"""Feedback and learning (mcp/sfp_learn.py): what is stored, what the model learns, and that it helps.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['SFP_ROOT'] = ROOT
sys.path.insert(0, os.path.join(ROOT, 'mcp'))
import sfp_mcp as core  # noqa: E402
import sfp_stack as v1  # noqa: E402
import sfp_hive as sel  # noqa: E402
import sfp_learn as learn  # noqa: E402


def django_project(tmp):
    d = os.path.join(tmp, 'django')
    os.makedirs(os.path.join(d, 'shop'), exist_ok=True)
    with open(os.path.join(d, 'requirements.txt'), 'w') as f:
        f.write('django>=5\npsycopg2-binary\ncelery\n')
    for name in ('manage.py', os.path.join('shop', 'models.py')):
        open(os.path.join(d, name), 'w').close()
    return d


class IsolatedData(unittest.TestCase):
    """Every test gets its own data folder, so nothing touches the real ~/.sfp."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {k: os.environ.get(k) for k in ('SFP_USAGE_LOG', 'SFP_NO_LEARNING', 'SFP_NO_USAGE_LOG', 'SFP_LEARN_WORDS')}
        for k in ('SFP_NO_LEARNING', 'SFP_NO_USAGE_LOG', 'SFP_LEARN_WORDS'):
            os.environ.pop(k, None)
        os.environ['SFP_USAGE_LOG'] = os.path.join(self.tmp.name, 'data', 'usage.jsonl')
        learn._CACHE.clear()
        self.project = django_project(self.tmp.name)

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        learn._CACHE.clear()
        self.tmp.cleanup()

    def data(self, name):
        return os.path.join(self.tmp.name, 'data', name)

    def lines(self, name):
        with open(self.data(name), encoding='utf-8') as f:
            return [json.loads(x) for x in f]

    def decide(self, task='write tests for the order view'):
        return learn.decide(task, self.project)

    def names(self, res):
        return [c['name'] for c in res['stack']]


class ModelTest(unittest.TestCase):
    def test_no_feedback_means_no_opinion(self):
        m = learn.Model()
        self.assertEqual(m.preference('django-tdd', ['test', 'order']), 0.0)
        self.assertEqual(m.recall(['test', 'order']), {})

    def test_with_no_feedback_the_selection_is_exactly_the_unlearned_one(self):
        hist = sel.History(v1.RECIPES, [])
        with tempfile.TemporaryDirectory() as tmp:
            project = django_project(tmp)
            plain = sel.select('write tests for the order view', project, history=hist)
            empty = sel.select('write tests for the order view', project, history=hist, model=learn.Model())
        self.assertEqual([(c['name'], c['score']) for c in plain['stack']], [(c['name'], c['score']) for c in empty['stack']])

    def test_a_helped_example_raises_and_an_unhelpful_one_lowers_the_preference(self):
        words = ['test', 'order', 'view']
        m = learn.fit([(learn.features('django-tdd', words), 1, 1.0), (learn.features('django-celery', words), 0, 1.0)])
        self.assertGreater(m.preference('django-tdd', words), 0.2)
        self.assertLess(m.preference('django-celery', words), -0.2)

    def test_one_report_is_damped_and_several_move_a_skill_further(self):
        words = ['test', 'order', 'view']
        one = learn.fit([(learn.features('django-tdd', words), 1, 1.0)]).preference('django-tdd', words)
        three = learn.fit([(learn.features('django-tdd', words), 1, 1.0)] * 3).preference('django-tdd', words)
        self.assertGreater(three, one)
        self.assertLess(one, 0.9)

    def test_the_preference_is_bounded(self):
        words = ['test', 'order', 'view', 'checkout', 'form']
        m = learn.fit([(learn.features('django-tdd', words), 1, 1.0)] * 500)
        self.assertLessEqual(m.preference('django-tdd', words), learn.MAX_PREFERENCE)

    def test_it_conditions_on_the_task_words(self):
        """A skill that helped for tasks about orders is not favoured for tasks about something else."""
        m = learn.fit([(learn.features('django-tdd', ['test', 'order', 'view']), 1, 1.0)] * 2)
        self.assertGreater(m.preference('django-tdd', ['test', 'order']), 0.2)
        self.assertEqual(m.preference('django-tdd', ['deploy', 'container']), 0.0)

    def test_ignored_counts_for_less_than_unhelpful(self):
        words = ['test', 'order']
        ignored = learn.fit([(learn.features('rust-testing', words), 0, learn.VERDICT_WEIGHT['ignored'])])
        unhelpful = learn.fit([(learn.features('rust-testing', words), 0, learn.VERDICT_WEIGHT['unhelpful'])])
        self.assertGreater(ignored.preference('rust-testing', words), unhelpful.preference('rust-testing', words))
        self.assertLess(ignored.preference('rust-testing', words), 0)

    def test_older_feedback_counts_for_less(self):
        now = time.time()
        fb = lambda age: [{'t': now - age * 86400, 'decision': 'd_x', 'skill': 'django-tdd', 'verdict': 'helped'}]  # noqa: E731
        decisions = {'d_x': {'id': 'd_x', 'stack': [], 'words': ['test', 'order']}}
        fresh = learn.fit(learn.build_examples(decisions, fb(1), now=now))
        old = learn.fit(learn.build_examples(decisions, fb(240), now=now))
        self.assertGreater(fresh.preference('django-tdd', ['test', 'order']), old.preference('django-tdd', ['test', 'order']))
        self.assertEqual(learn.build_examples(decisions, fb(learn.MAX_FEEDBACK_AGE_DAYS + 5), now=now), [])

    def test_the_latest_verdict_for_a_skill_in_a_decision_wins(self):
        now = time.time()
        decisions = {'d_x': {'id': 'd_x', 'stack': [], 'words': ['test']}}
        fb = [{'t': now - 10, 'decision': 'd_x', 'skill': 'django-tdd', 'verdict': 'unhelpful'},
              {'t': now, 'decision': 'd_x', 'skill': 'django-tdd', 'verdict': 'helped'}]
        examples = learn.build_examples(decisions, fb, now=now)
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0][1], 1)


class PrivacyTest(IsolatedData):
    def test_a_decision_stores_numbers_and_word_stems_not_the_task_or_paths(self):
        res = self.decide('write tests for my secret-project order view')
        row = self.lines('decisions.jsonl')[0]
        text = json.dumps(row)
        self.assertNotIn('secret-project', text)
        self.assertNotIn(self.project, text)
        self.assertNotIn('write tests for my', text)
        self.assertEqual(set(row), {'id', 't', 'v', 'engine', 'tech', 'phases', 'stack', 'cand', 'words'})
        self.assertEqual(row['id'], res['decision'])
        self.assertIn('order', row['words'])

    def test_words_can_be_switched_off(self):
        os.environ['SFP_LEARN_WORDS'] = '0'
        self.decide()
        self.assertNotIn('words', self.lines('decisions.jsonl')[0])

    def test_without_words_feedback_cannot_teach_and_says_so(self):
        os.environ['SFP_LEARN_WORDS'] = '0'
        res = self.decide()
        out = learn.give_feedback(res['decision'], helped=['django-tdd'])
        self.assertIn('note', out)
        self.assertEqual(out['examples'], 0)

    def test_words_can_be_given_with_the_feedback_instead(self):
        os.environ['SFP_LEARN_WORDS'] = '1'
        res = self.decide()
        rows = self.lines('decisions.jsonl')
        for r in rows:
            r.pop('words')                      # a decision made by a client that kept no words
        with open(self.data('decisions.jsonl'), 'w') as f:
            f.write(''.join(json.dumps(r) + '\n' for r in rows))
        learn._CACHE.clear()
        without = learn.give_feedback(res['decision'], helped=['django-tdd'])
        self.assertEqual(without['examples'], 0)
        out = learn.give_feedback(res['decision'], helped=['django-tdd'], task='write tests for the order view')
        self.assertGreater(out['examples'], 0)
        self.assertIn('words', self.lines('feedback.jsonl')[-1])

    def test_the_kill_switches_record_and_learn_nothing(self):
        for var in ('SFP_NO_LEARNING', 'SFP_NO_USAGE_LOG'):
            os.environ[var] = '1'
            res = self.decide()
            self.assertIsNone(res['decision'])
            self.assertFalse(res['learning']['enabled'])
            self.assertEqual(learn.give_feedback(None, helped=['django-tdd'])['recorded'], 0)
            self.assertFalse(os.path.exists(self.data('decisions.jsonl')))
            os.environ.pop(var)

    def test_forget_deletes_everything(self):
        res = self.decide()
        learn.give_feedback(res['decision'], helped=['django-tdd'])
        out = learn.forget()
        self.assertIn('decisions.jsonl', out['removed'])
        self.assertIn('feedback.jsonl', out['removed'])
        self.assertFalse(os.path.exists(self.data('decisions.jsonl')))
        self.assertEqual(learn.status()['decisions'], 0)


class FeedbackTest(IsolatedData):
    def test_unknown_decision_and_unknown_skill_are_rejected_clearly(self):
        with self.assertRaises(ValueError) as e:
            learn.give_feedback('d_nope', helped=['django-tdd'])
        self.assertIn('no decision', str(e.exception))
        res = self.decide()
        with self.assertRaises(ValueError) as e:
            learn.give_feedback(res['decision'], helped=['no-such-skill'])
        self.assertIn('no skill named', str(e.exception))

    def test_a_skill_cannot_be_both_helped_and_unhelpful(self):
        res = self.decide()
        with self.assertRaises(ValueError):
            learn.give_feedback(res['decision'], helped=['django-tdd'], unhelpful=['django-tdd'])

    def test_empty_feedback_is_rejected(self):
        res = self.decide()
        with self.assertRaises(ValueError):
            learn.give_feedback(res['decision'])

    def test_last_means_the_most_recent_decision(self):
        self.decide('write tests for the order view')
        second = self.decide('add a column to a big table')
        out = learn.give_feedback('last', helped=['database-migrations'])
        self.assertEqual(out['decision'], second['decision'])

    def test_the_response_shows_how_the_model_moved(self):
        res = self.decide()
        out = learn.give_feedback(res['decision'], helped=['django-tdd'], unhelpful=['django-celery'])
        moved = {m['skill']: m for m in out['moved']}
        self.assertGreater(moved['django-tdd']['after'], moved['django-tdd']['before'])
        self.assertLess(moved['django-celery']['after'], moved['django-celery']['before'])

    def test_corrupt_and_foreign_lines_are_ignored(self):
        self.decide()
        with open(self.data('feedback.jsonl'), 'w') as f:
            f.write('not json\n{"skill": "no-such-skill", "verdict": "helped"}\n{"skill": "django-tdd", "verdict": "bogus"}\n')
        self.assertEqual(learn.load_feedback(), [])
        self.assertEqual(learn.status()['examples'], 0)

    def test_the_log_is_compacted_when_it_grows_too_large(self):
        os.makedirs(os.path.dirname(self.data('x')), exist_ok=True)
        with open(self.data('decisions.jsonl'), 'w') as f:
            for i in range(int(learn.MAX_DECISIONS * 1.5) + 10):
                f.write(json.dumps({'id': 'd_%d' % i, 'stack': []}) + '\n')
        learn._compact_decisions()
        self.assertEqual(len(self.lines('decisions.jsonl')), learn.MAX_DECISIONS)


class LearningLoopTest(IsolatedData):
    def test_a_reported_mistake_is_fixed_next_time(self):
        first = self.decide()
        self.assertIn('django-celery', self.names(first))       # the known flaw
        learn.give_feedback(first['decision'], helped=['django-tdd'], unhelpful=['django-celery'])
        second = self.decide()
        self.assertNotIn('django-celery', self.names(second))
        self.assertIn('django-tdd', self.names(second))
        self.assertIn('preferred from feedback', ' '.join(second['stack'][0]['reasons']))

    def test_an_unrelated_task_is_not_disturbed(self):
        first = self.decide()
        learn.give_feedback(first['decision'], helped=['django-tdd'], unhelpful=['django-celery'])
        other = self.decide('set up background jobs with celery')
        self.assertIn('django-celery', self.names(other))

    def test_a_skill_the_search_missed_is_found_after_it_is_reported_missing(self):
        task = 'scrape product prices from websites'
        before = self.names(learn.decide(task))
        self.assertNotIn('data-scraper-agent', before)
        res = learn.decide(task)
        for _ in range(2):
            learn.give_feedback(res['decision'], missing=['data-scraper-agent'])
        self.assertIn('data-scraper-agent', self.names(learn.decide(task)))

    def test_a_similar_task_benefits_too(self):
        first = self.decide('write tests for the order view')
        learn.give_feedback(first['decision'], helped=['django-tdd'], unhelpful=['django-celery'])
        similar = self.decide('add tests for the order view')
        self.assertNotIn('django-celery', self.names(similar))

    def test_no_single_report_can_remove_the_only_good_skill(self):
        res = learn.decide('write table driven tests in Go')
        learn.give_feedback(res['decision'], unhelpful=['golang-testing'])
        self.assertIn('golang-testing', self.names(learn.decide('write table driven tests in Go')))

    def test_turning_learning_off_for_one_call_ignores_the_model(self):
        first = self.decide()
        learn.give_feedback(first['decision'], helped=['django-tdd'], unhelpful=['django-celery'])
        plain = learn.decide('write tests for the order view', self.project, learn=False)
        self.assertEqual(self.names(plain), self.names(first))
        self.assertFalse(plain['learning']['enabled'])

    def test_helped_stacks_feed_the_history_signal(self):
        first = self.decide('add an endpoint to list orders and migrate the table')
        names = self.names(first)
        learn.give_feedback(first['decision'], helped=names)
        events = learn.history_events()
        self.assertTrue({e['skill'] for e in events} >= set(names))

    def test_status_reports_what_was_learned(self):
        first = self.decide()
        learn.give_feedback(first['decision'], helped=['django-tdd'], unhelpful=['django-celery'])
        st = learn.status()
        self.assertEqual(st['decisions'], 1)
        self.assertEqual(st['feedback']['helped'], 1)
        self.assertEqual(st['feedback']['unhelpful'], 1)
        self.assertTrue(any(x['skill'] == 'django-tdd' for x in st['learned_for']))
        self.assertTrue(any(x['skill'] == 'django-celery' for x in st['learned_against']))
        text = learn.format_status(st)
        self.assertIn('Now favours', text)
        self.assertIn('Now avoids', text)

    def test_status_with_nothing_recorded_says_how_to_start(self):
        self.assertIn('Give feedback', learn.format_status(learn.status()))

    def test_the_helped_rate_is_split_only_when_there_is_enough_data(self):
        first = self.decide()
        learn.give_feedback(first['decision'], helped=['django-tdd'], unhelpful=['django-celery'])
        hr = learn.status()['helped_rate']
        self.assertIsNone(hr['older'])
        self.assertEqual(hr['all'], 0.5)


class LearningCurveTest(unittest.TestCase):
    """Does learning help on tasks it has not seen? Pinned to what was measured, so a regression fails."""

    @classmethod
    def setUpClass(cls):
        cls.lc = learn.learning_curve(os.path.join(ROOT, 'tests'))

    def test_reported_mistakes_are_mostly_fixed_when_the_same_task_is_asked_again(self):
        self.assertGreaterEqual(self.lc['training_mistakes_fixed_on_retry'], 0.80)

    def test_learning_does_not_make_unseen_tasks_worse_on_average(self):
        self.assertGreaterEqual(self.lc['gain'], 0.0)
        self.assertGreater(self.lc['folds_improved'], self.lc['folds_worse'])

    def test_it_never_introduces_a_wrong_technology(self):
        self.assertEqual(self.lc['wrong_technology_stacks_heldout'], 0)

    def test_few_correct_tasks_are_spoiled(self):
        evaluated = self.lc['tasks'] * self.lc['repeats']
        self.assertLess(self.lc['heldout_tasks_that_got_worse'] / evaluated, 0.03)


class McpRoundTripTest(IsolatedData):
    """The loop through a real MCP server over stdio: select, give feedback, select again, read the status."""

    def test_the_loop_works_over_mcp(self):
        env = dict(os.environ, SFP_ROOT=ROOT)
        p = subprocess.Popen([sys.executable, '-I', os.path.join(ROOT, 'mcp', 'sfp_mcp.py')], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)

        def call(i, tool, **args):
            p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': i, 'method': 'tools/call',
                                      'params': {'name': tool, 'arguments': args}}) + '\n')
            p.stdin.flush()
            r = json.loads(p.stdout.readline())['result']
            return r['isError'], r['content'][0]['text']

        try:
            err, text = call(1, 'select_skills', task='write tests for the order view', project_path=self.project)
            self.assertFalse(err, text)
            first = json.loads(text)
            self.assertIn('django-celery', self.names(first))
            self.assertTrue(first['decision'])
            err, text = call(2, 'give_feedback', decision=first['decision'], helped='django-tdd', unhelpful='django-celery')
            self.assertFalse(err, text)
            self.assertEqual(json.loads(text)['recorded'], 2)
            err, text = call(3, 'select_skills', task='write tests for the order view', project_path=self.project)
            second = json.loads(text)
            self.assertNotIn('django-celery', self.names(second))
            err, text = call(4, 'learning_status')
            self.assertFalse(err, text)
            self.assertEqual(json.loads(text)['feedback']['unhelpful'], 1)
            err, text = call(5, 'give_feedback', decision='d_nope', helped='django-tdd')
            self.assertTrue(err)
            err, text = call(6, 'select_skills', task='x', project_path='/no/such/folder')
            self.assertTrue(err)
            err, _ = call(7, 'get_skill', name='api-design')
            err, text = call(8, 'predict_next')   # defaults to the last skill fetched in this session
            self.assertEqual(json.loads(text)['after'], 'api-design')
            self.assertEqual(json.loads(text)['next'][0]['name'], 'database-migrations')
        finally:
            p.stdin.close()
            p.wait(timeout=10)
            p.stdout.close()
            p.stderr.close()


class CommandLineTest(IsolatedData):
    def run_cli(self, *args):
        env = dict(os.environ, SFP_ROOT=ROOT)
        return subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'mcp', 'sfp_hive.py')] + list(args),
                              capture_output=True, text=True, env=env, timeout=60)

    def test_hive_feedback_status_forget(self):
        done = self.run_cli('select', 'write tests for the order view', '--project', self.project, '--json')
        self.assertEqual(done.returncode, 0, done.stderr)
        did = json.loads(done.stdout)['decision']
        done = self.run_cli('feedback', did, '--helped', 'django-tdd', '--unhelpful', 'django-celery')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)['recorded'], 2)
        done = self.run_cli('status')
        self.assertIn('Now avoids: django-celery', done.stdout)
        done = self.run_cli('forget')
        self.assertIn('feedback.jsonl', done.stdout)

    def test_linucb_exploration(self):
        m = learn.fit([(learn.features('django-tdd', ['test', 'view']), 1, 1.0)])
        self.assertGreater(m.examples, 0)
        u = m.uncertainty('django-tdd', ['test', 'view'])
        self.assertGreater(u, 0.0)
        base_p = m.preference('django-tdd', ['test', 'view'], explore=0.0)
        explore_p = m.preference('django-tdd', ['test', 'view'], explore=0.5)
        self.assertGreaterEqual(explore_p, base_p)

    def test_record_reward(self):
        row = learn.record_reward('django-tdd', 0.8, task='write tests', source='test_passed')
        self.assertIsNotNone(row)
        self.assertEqual(row['verdict'], 'helped')
        self.assertEqual(row['reward'], 0.8)
        self.assertEqual(row['source'], 'test_passed')
        row_neg = learn.record_reward('django-celery', -0.5, task='write tests', source='test_failed')
        self.assertEqual(row_neg['verdict'], 'unhelpful')


if __name__ == '__main__':
    unittest.main()

