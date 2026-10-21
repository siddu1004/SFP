"""The stack engine (mcp/sfp_stack.py): project fingerprints, stack rules, the Markov chain and its quality floors.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['SFP_ROOT'] = ROOT
sys.path.insert(0, os.path.join(ROOT, 'mcp'))
import sfp_mcp as core  # noqa: E402
import sfp_stack as st  # noqa: E402

EVAL = json.load(open(os.path.join(ROOT, 'tests', 'stack_eval.json'), encoding='utf-8'))


def make_project(tmp, name):
    for rel, body in EVAL['projects'][name].items():
        f = os.path.join(tmp, name, rel)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(body)
    return os.path.join(tmp, name)


class FixtureTest(unittest.TestCase):
    def test_recipes_and_eval_cases_name_real_skills(self):
        raw = json.load(open(os.path.join(ROOT, 'mcp', 'stack_recipes.json'), encoding='utf-8'))
        for r in raw['recipes']:
            for n in r['skills']:
                self.assertIn(n, core.SKILLS, 'recipe %s' % r['name'])
        self.assertEqual(len(st.RECIPES), len(raw['recipes']))
        for c in EVAL['cases']:
            for n in c['expect'] + c['avoid']:
                self.assertIn(n, core.SKILLS, c['task'])


class ProjectScanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = {p: make_project(cls.tmp.name, p) for p in EVAL['projects']}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def terms(self, name):
        return st.scan_project(self.paths[name])['terms']

    def test_each_stack_is_recognised(self):
        # Terms are stored stemmed, the way search compares them (postgres -> postgr).
        expect = {'nextjs': ['nextj', 'react', 'playwright'], 'django': ['django', 'python', 'postgr', 'celery'],
                  'fastapi': ['fastapi', 'python', 'redi'], 'go': ['golang', 'docker'], 'spring': ['springboot', 'java', 'jpa'],
                  'flutter': ['flutter', 'dart'], 'android': ['android', 'kotlin', 'compos'], 'rust': ['rust'],
                  'laravel': ['laravel', 'php'], 'vue': ['vue', 'vite']}
        for proj, want in expect.items():
            got = self.terms(proj)
            for w in want:
                self.assertIn(w, got, '%s should detect %s, got %s' % (proj, w, sorted(got)))

    def test_frameworks_outweigh_their_language(self):
        t = self.terms('django')
        self.assertGreater(t['django'], t['python'])

    def test_skips_dependency_folders(self):
        nm = os.path.join(self.paths['go'], 'node_modules', 'react')
        os.makedirs(nm, exist_ok=True)
        with open(os.path.join(nm, 'package.json'), 'w') as f:
            f.write('{"dependencies": {"react": "1"}}')
        self.assertNotIn('react', self.terms('go'))

    def test_missing_folder_is_empty_not_an_error(self):
        self.assertEqual(st.scan_project('/no/such/folder')['terms'], {})


class StackRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = {p: make_project(cls.tmp.name, p) for p in EVAL['projects']}
        cls.chain = st.Markov(st.RECIPES, [])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def stack(self, task, project=None, **kw):
        return st.recommend(task, self.paths.get(project), chain=self.chain, **kw)

    def test_same_words_different_project_different_skills(self):
        names = {p: {c['name'] for c in self.stack('write tests for the order view', p)['stack']}
                 for p in ('nextjs', 'django', 'go', 'rust')}
        self.assertIn('react-testing', names['nextjs'])
        self.assertIn('golang-testing', names['go'])
        self.assertIn('rust-testing', names['rust'])
        self.assertTrue({'django-tdd', 'python-testing'} & names['django'])
        self.assertEqual(len({frozenset(v) for v in names.values()}), 4)

    def test_never_stacks_a_skill_for_another_technology(self):
        res = self.stack('write tests', 'flutter')
        for c in res['stack']:
            tech = st.SKILL_TECH[c['name']]
            self.assertFalse(tech and not (tech & {'flutter', 'dart'}), c['name'])

    def test_naming_a_technology_overrides_the_project(self):
        names = [c['name'] for c in self.stack('add tests in Django', 'nextjs')['stack']]
        self.assertTrue({'django-tdd', 'python-testing'} & set(names), names)

    def test_stack_is_ordered_by_phase_of_work(self):
        res = self.stack('design the api, build it, test it and deploy it', 'fastapi', max_skills=6)
        order = [st.PHASE_ORDER.index(c['phase']) for c in res['stack']]
        self.assertEqual(order, sorted(order))
        for c in res['stack']:
            self.assertEqual(c['layer'], st.LAYER[c['phase']])

    def test_budget_and_size_are_respected(self):
        res = self.stack('review security, tests and performance of this service', 'go', budget=5000, max_skills=3)
        self.assertLessEqual(len(res['stack']), 3)
        if len(res['stack']) > 1:
            self.assertLessEqual(res['tokens'], 5000)
        self.assertEqual(res['tokens'], sum(c['tokens'] for c in res['stack']))

    def test_one_skill_per_role(self):
        res = self.stack('build an MCP server for our ticket system')
        slots = [(c['category'], c['phase']) for c in res['stack']]
        self.assertEqual(len(slots), len(set(slots)), res['stack'])

    def test_at_most_one_named_visual_style(self):
        res = self.stack('make it brutalist and glassmorphism and retro and neon', max_skills=6)
        styles = [c for c in res['stack'] if c['category'] == 'design-styles']
        self.assertLessEqual(len(styles), 2)  # two named styles are allowed, never more
        res = self.stack('make the landing page look premium', max_skills=6)
        self.assertLessEqual(sum(c['category'] == 'design-styles' for c in res['stack']), 1)

    def test_skills_already_used_are_not_offered_again(self):
        res = self.stack('write tests for the routes', 'fastapi', after=['python-testing'])
        self.assertNotIn('python-testing', [c['name'] for c in res['stack']])

    def test_nothing_relevant_gives_an_empty_stack(self):
        self.assertEqual(self.stack('for the of a')['stack'], [])

    def test_every_stack_member_says_why(self):
        for c in self.stack('write tests for the signup form', 'nextjs')['stack']:
            self.assertTrue(c['reasons'])
            self.assertTrue(os.path.isfile(os.path.join(ROOT, c['path'])))

    def test_is_fast(self):
        res = self.stack('add a new endpoint with validation', 'fastapi')
        self.assertLess(res['ms'], 500)


class MarkovTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, 'usage.jsonl')
        os.environ['SFP_USAGE_LOG'] = self.log
        os.environ.pop('SFP_NO_USAGE_LOG', None)

    def tearDown(self):
        os.environ.pop('SFP_USAGE_LOG', None)
        self.tmp.cleanup()

    def test_rows_are_probability_distributions(self):
        m = st.Markov(st.RECIPES, [])
        for a in ('design-taste-frontend', 'career-ops', 'golang-testing', 'sfp'):
            total = sum(m.prob(a, b) for b in core.SKILLS)
            self.assertAlmostEqual(total, 1.0, places=6, msg=a)

    def test_recipes_seed_the_chain(self):
        m = st.Markov(st.RECIPES, [])
        self.assertEqual(m.next('design-taste-frontend', 1)[0][1], 'impeccable')
        self.assertEqual(m.next('api-design', 1)[0][1], 'database-migrations')

    def test_recorded_usage_changes_predictions(self):
        before = st.model().next('golang-testing', 1)[0][1]
        self.assertNotEqual(before, 'docker-patterns')
        for i in range(4):
            st.record('golang-testing', session='s%d' % i)
            st.record('docker-patterns', session='s%d' % i)
        self.assertEqual(st.model().next('golang-testing', 1)[0][1], 'docker-patterns')

    def test_outcomes_move_the_prior(self):
        for _ in range(3):
            st.record('tdd-workflow', 'helped')
        st.record('cpp-testing', 'unhelpful')
        m = st.model()
        self.assertGreater(m.prior('tdd-workflow'), 0.2)
        self.assertLess(m.prior('cpp-testing'), 0)
        self.assertEqual(m.prior('react-testing'), 0)

    def test_log_holds_names_and_times_only(self):
        st.record('react-testing', 'helped', session='abc')
        with open(self.log) as f:
            event = json.loads(f.read().strip())
        self.assertEqual(set(event), {'t', 'skill', 'outcome', 'session'})
        st.recommend('a secret prompt about my-private-repo', chain=st.model())
        with open(self.log) as f:
            self.assertNotIn('secret', f.read())

    def test_logging_can_be_turned_off(self):
        os.environ['SFP_NO_USAGE_LOG'] = '1'
        try:
            self.assertFalse(st.record('react-testing')['recorded'])
            self.assertFalse(os.path.exists(self.log))
        finally:
            os.environ.pop('SFP_NO_USAGE_LOG')

    def test_unknown_skills_are_rejected_and_bad_lines_ignored(self):
        with self.assertRaises(ValueError):
            st.record('no-such-skill')
        with open(self.log, 'w') as f:
            f.write('not json\n{"skill": "no-such-skill"}\n{"t": 1, "skill": "tdd-workflow"}\n')
        self.assertEqual(len(st.read_usage()), 1)


class QualityFloorTest(unittest.TestCase):
    """The README quotes these figures; a change that makes the engine worse fails here."""

    @classmethod
    def setUpClass(cls):
        cls.ev = st.evaluate(os.path.join(ROOT, 'tests'))

    def test_without_a_project_it_is_at_least_as_good_as_search(self):
        self.assertGreaterEqual(self.ev['bench_hit'], 0.85)
        self.assertGreaterEqual(self.ev['bench_hit'], self.ev['bench_search_hit'])
        self.assertGreaterEqual(self.ev['bench_first'], 0.75)

    def test_stacks_stay_small(self):
        self.assertLessEqual(self.ev['avg_size'], 3.0)
        self.assertLessEqual(self.ev['avg_tokens'], 12000)

    def test_with_a_project_it_finds_the_right_skill_and_never_the_wrong_technology(self):
        self.assertGreaterEqual(self.ev['proj_hit'], 0.75)
        self.assertGreater(self.ev['proj_hit'], self.ev['proj_search_hit'])
        self.assertEqual(self.ev['proj_wrong'], 0)


class InterfacesTest(unittest.TestCase):
    def run_cli(self, *args, env=None):
        script = os.path.join(ROOT, 'templates', 'sfp-manager', 'scripts', 'stack.py')
        e = dict(os.environ, SFP_ROOT=ROOT, **(env or {}))
        return subprocess.run([sys.executable, '-I', script] + list(args), capture_output=True, text=True, env=e, timeout=60)

    def test_skill_launcher_runs_the_engine(self):
        done = self.run_cli('recommend', 'write table driven tests', '--json')
        self.assertEqual(done.returncode, 0, done.stderr)
        res = json.loads(done.stdout)
        self.assertIn('golang-testing', [c['name'] for c in res['stack']])
        done = self.run_cli('recipes')
        self.assertIn('ship-a-service', done.stdout)

    def test_mcp_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_project(tmp, 'django')
            log = os.path.join(tmp, 'usage.jsonl')
            env = dict(os.environ, SFP_ROOT=ROOT, SFP_USAGE_LOG=log)
            p = subprocess.Popen([sys.executable, '-I', os.path.join(ROOT, 'mcp', 'sfp_mcp.py')], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)

            def call(i, tool, **args):
                p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': i, 'method': 'tools/call',
                                          'params': {'name': tool, 'arguments': args}}) + '\n')
                p.stdin.flush()
                r = json.loads(p.stdout.readline())['result']
                return r['isError'], r['content'][0]['text']

            try:
                err, text = call(1, 'recommend_stack', task='write tests for the order view', project_path=proj)
                self.assertFalse(err, text)
                res = json.loads(text)
                self.assertIn('django', res['project']['technologies'])
                self.assertIn('postgres', res['project']['technologies'])
                self.assertTrue({'django-tdd', 'python-testing'} & {c['name'] for c in res['stack']})
                err, _ = call(2, 'get_skill', name='api-design')
                self.assertFalse(err)
                err, text = call(3, 'predict_next')  # defaults to the last skill fetched in this session
                self.assertFalse(err, text)
                self.assertEqual(json.loads(text)['after'], 'api-design')
                self.assertEqual(json.loads(text)['next'][0]['name'], 'database-migrations')
                err, text = call(4, 'record_usage', skill='api-design', outcome='helped')
                self.assertFalse(err, text)
                self.assertTrue(os.path.isfile(log))
                err, text = call(5, 'recommend_stack', task='x', project_path='/no/such/folder')
                self.assertTrue(err)
            finally:
                p.stdin.close()
                p.wait(timeout=10)
                p.stdout.close()
                p.stderr.close()


if __name__ == '__main__':
    unittest.main()
