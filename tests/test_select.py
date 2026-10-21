"""The selector (mcp/sfp_select.py): agreement, overlap, role allocation, history, and quality floors.

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
import sfp_select as sel  # noqa: E402

with open(os.path.join(ROOT, 'tests', 'select_heldout.json'), encoding='utf-8') as _f:
    HELDOUT = json.load(_f)


class SelectionRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        sel._projects(HELDOUT, cls.tmp.name)
        cls.hist = sel.History(v1.RECIPES, [])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def project(self, name):
        return os.path.join(self.tmp.name, name)

    def select(self, task, project=None, **kw):
        return sel.select(task, self.project(project) if project else None, history=self.hist, **kw)

    def test_heldout_cases_name_real_skills(self):
        for c in HELDOUT['cases']:
            for n in c['expect'] + c['avoid']:
                self.assertIn(n, core.SKILLS, c['task'])

    def test_agreement_needs_strong_words_or_two_signals(self):
        weak_alone = {'words': 0.5, 'project': None, 'role': 0.1, 'category': None, 'history': None, 'relation': 'general'}
        self.assertFalse(sel.has_agreement(weak_alone))
        self.assertTrue(sel.has_agreement(dict(weak_alone, role=0.9)))
        self.assertTrue(sel.has_agreement(dict(weak_alone, words=0.9)))
        self.assertFalse(sel.has_agreement(dict(weak_alone, words=0.0, role=0.9, category=0.9)))
        self.assertFalse(sel.has_agreement(dict(weak_alone, words=1.0, relation='mismatch')))

    def test_relation_to_the_project(self):
        self.assertEqual(sel.relation({'django'}, {'django', 'python'}), 'fit')
        self.assertEqual(sel.relation({'django'}, {'react', 'javascript'}), 'mismatch')
        self.assertEqual(sel.relation(set(), {'react'}), 'general')
        self.assertEqual(sel.relation({'django'}, set()), 'unasked')
        # Only a language in sight: a framework of that language is plausible.
        self.assertEqual(sel.relation({'swiftui'}, {'swift'}), 'near')
        self.assertEqual(sel.relation({'swiftui'}, {'swift', 'react'}), 'mismatch')

    def test_response_function(self):
        self.assertAlmostEqual(sel.respond(0.5, 0.5), 0.5)
        self.assertGreater(sel.respond(1.0, 0.5), sel.respond(0.5, 0.5))
        self.assertEqual(sel.respond(0.0, 0.5), 0.0)

    def test_overlapping_skills_are_not_both_chosen(self):
        names = [c['name'] for c in self.select('build an MCP server for our ticket system')['stack']]
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                self.assertLess(v1.similarity(a, b), 0.6, (a, b))

    def test_no_job_takes_more_than_two_skills(self):
        res = self.select('write tests for the routes', 'mcp', max_skills=8)
        jobs = [c['phase'] for c in res['stack']]
        for p in set(jobs):
            self.assertLessEqual(jobs.count(p), 2, jobs)

    def test_same_words_different_project(self):
        names = {p: {c['name'] for c in self.select('write tests for the orders', p)['stack']}
                 for p in ('dotnet', 'ios', 'ml', 'quarkus')}
        self.assertIn('csharp-testing', names['dotnet'])
        self.assertIn('swift-protocol-di-testing', names['ios'])
        self.assertIn('python-testing', names['ml'])
        for p in ('ios', 'ml', 'quarkus'):
            self.assertNotIn('csharp-testing', names[p])

    def test_never_offers_the_selector_or_router(self):
        for task in ('decide which skills to use', 'select skills for this task', 'sfp select'):
            names = {c['name'] for c in self.select(task)['stack']}
            self.assertFalse(names & {'sfp', 'sfp-select'}, task)

    def test_empty_for_filler(self):
        self.assertEqual(self.select('for the of a')['stack'], [])

    def test_every_member_explains_itself(self):
        res = self.select('add a module for refunds', 'nestjs')
        self.assertTrue(res['stack'])
        for c in res['stack']:
            self.assertTrue(any(r.startswith('backed by:') for r in c['reasons']))
            self.assertTrue(os.path.isfile(os.path.join(ROOT, c['path'])))
        self.assertIn('analysis', res)

    def test_stack_is_ordered_by_phase_and_respects_the_budget(self):
        res = self.select('design the api, build it, test it and deploy it', 'nestjs', max_skills=6, budget=9000)
        order = [v1.PHASE_ORDER.index(c['phase']) for c in res['stack']]
        self.assertEqual(order, sorted(order))
        if len(res['stack']) > 1:
            self.assertLessEqual(res['tokens'], 9000)

    def test_project_scan_is_cached(self):
        p = self.project('rails')
        sel._SCANS.pop(os.path.abspath(p), None)
        first = sel.scan(p)
        self.assertIs(sel.scan(p), first)

    def test_a_decision_is_fast(self):
        res = self.select('roll out the new version without downtime', 'infra')
        self.assertLess(res['ms'], 500)


class HistoryTest(unittest.TestCase):
    def test_rows_are_distributions(self):
        hist = sel.History(v1.RECIPES, [])
        for a in ('api-design', 'career-ops', 'swiftui-patterns'):
            self.assertAlmostEqual(sum(hist.prob(a, b) for b in core.SKILLS), 1.0, places=6)

    def test_older_sequences_fade(self):
        now = time.time()
        old = [{'t': now - 120 * 86400, 'skill': 'golang-testing', 'session': 'old'},
               {'t': now - 120 * 86400, 'skill': 'docker-patterns', 'session': 'old'}]
        new = [{'t': now, 'skill': 'golang-testing', 'session': 'new'},
               {'t': now, 'skill': 'canary-watch', 'session': 'new'}]
        hist = sel.History(v1.RECIPES, old + new, now=now)
        self.assertGreater(hist.prob('golang-testing', 'canary-watch'), hist.prob('golang-testing', 'docker-patterns'))
        # A four-month-old sequence is worth about 1/16 of a new one.
        self.assertAlmostEqual(hist.c['golang-testing']['docker-patterns'], 2 ** -4, places=3)

    def test_a_recorded_sequence_becomes_the_prediction(self):
        now = time.time()
        events = []
        for i in range(3):
            events += [{'t': now, 'skill': 'golang-testing', 'session': 's%d' % i},
                       {'t': now, 'skill': 'canary-watch', 'session': 's%d' % i}]
        self.assertEqual(sel.History(v1.RECIPES, events).next('golang-testing', 1)[0][1], 'canary-watch')


class QualityTest(unittest.TestCase):
    """The README quotes these figures; a change that makes the selector worse fails here."""

    @classmethod
    def setUpClass(cls):
        cls.ev = sel.evaluate(os.path.join(ROOT, 'tests'))

    def test_at_least_as_good_as_the_earlier_engine_and_search_everywhere(self):
        for key in ('bench', 'proj', 'fresh'):
            self.assertGreaterEqual(self.ev[key + '_select']['hit'], self.ev[key + '_v1']['hit'], key)
            self.assertGreaterEqual(self.ev[key + '_select']['hit'], self.ev[key + '_search']['hit'], key)

    def test_floors(self):
        self.assertGreaterEqual(self.ev['bench_select']['hit'], 0.85)
        self.assertGreaterEqual(self.ev['proj_select']['hit'], 0.75)
        self.assertGreaterEqual(self.ev['fresh_select']['hit'], 0.80)
        self.assertGreaterEqual(self.ev['bench_select']['first'], 0.75)

    def test_never_the_wrong_technology(self):
        for key in ('bench', 'proj', 'fresh'):
            self.assertEqual(self.ev[key + '_select']['wrong'], 0, key)

    def test_stacks_stay_small(self):
        for key in ('bench', 'proj', 'fresh'):
            self.assertLessEqual(self.ev[key + '_select']['size'], 2.6, key)


class InterfaceTest(unittest.TestCase):
    def run_launcher(self, *args):
        script = os.path.join(ROOT, 'templates', 'sfp-select', 'scripts', 'select_skills.py')
        with tempfile.TemporaryDirectory() as data:
            env = dict(os.environ, SFP_ROOT=ROOT, SFP_USAGE_LOG=os.path.join(data, 'usage.jsonl'))
            return subprocess.run([sys.executable, '-I', script] + list(args), capture_output=True, text=True, env=env, timeout=60)

    def test_the_skill_launcher_runs_the_selector(self):
        done = self.run_launcher('select', 'write table driven tests in Go', '--json')
        self.assertEqual(done.returncode, 0, done.stderr)
        res = json.loads(done.stdout)
        self.assertTrue(res['engine'].startswith('sfp-select'))
        self.assertIn('golang-testing', [c['name'] for c in res['stack']])
        self.assertTrue(res['decision'])

    def test_the_earlier_engine_is_still_available(self):
        done = self.run_launcher('select', 'write tests', '--engine', 'v1', '--json')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn('engine', json.loads(done.stdout))


if __name__ == '__main__':
    unittest.main()
