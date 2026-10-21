"""The hive (mcp/sfp_hive.py): each colony mechanism, learning, evaporation, and quality floors against v1.

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
import sfp_hive as hive  # noqa: E402

with open(os.path.join(ROOT, 'tests', 'hive_fresh.json'), encoding='utf-8') as _f:
    FRESH = json.load(_f)


class MechanismTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        hive._projects(FRESH, cls.tmp.name)
        cls.col = hive.Colony(v1.RECIPES, [])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def project(self, name):
        return os.path.join(self.tmp.name, name)

    def test_fresh_cases_name_real_skills(self):
        for c in FRESH['cases']:
            for n in c['expect'] + c['avoid']:
                self.assertIn(n, core.SKILLS, c['task'])

    def test_quorum_needs_strong_words_or_two_scouts(self):
        weak_alone = {'words': 0.5, 'project': None, 'role': 0.1, 'category': None, 'trail': None, 'relation': 'general'}
        self.assertFalse(hive.has_quorum(weak_alone))
        self.assertTrue(hive.has_quorum(dict(weak_alone, role=0.9)))
        self.assertTrue(hive.has_quorum(dict(weak_alone, words=0.9)))
        self.assertFalse(hive.has_quorum(dict(weak_alone, words=0.0, role=0.9, category=0.9)))
        self.assertFalse(hive.has_quorum(dict(weak_alone, words=1.0, relation='mismatch')))

    def test_relation_to_the_project(self):
        self.assertEqual(hive.relation({'django'}, {'django', 'python'}), 'fit')
        self.assertEqual(hive.relation({'django'}, {'react', 'javascript'}), 'mismatch')
        self.assertEqual(hive.relation(set(), {'react'}), 'general')
        self.assertEqual(hive.relation({'django'}, set()), 'unasked')
        # Only a language in sight: a framework of that language is plausible.
        self.assertEqual(hive.relation({'swiftui'}, {'swift'}), 'near')
        self.assertEqual(hive.relation({'swiftui'}, {'swift', 'react'}), 'mismatch')

    def test_response_function(self):
        self.assertAlmostEqual(hive.respond(0.5, 0.5), 0.5)
        self.assertGreater(hive.respond(1.0, 0.5), hive.respond(0.5, 0.5))
        self.assertEqual(hive.respond(0.0, 0.5), 0.0)

    def test_stop_signals_keep_out_near_duplicates(self):
        res = hive.recommend('build an MCP server for our ticket system', chain=self.col)
        names = [c['name'] for c in res['stack']]
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                self.assertLess(v1.similarity(a, b), 0.6, (a, b))

    def test_no_job_takes_more_than_two(self):
        res = hive.recommend('write tests for the routes', self.project('mcp'), chain=self.col, max_skills=8)
        jobs = [c['phase'] for c in res['stack']]
        for p in set(jobs):
            self.assertLessEqual(jobs.count(p), 2, jobs)

    def test_same_words_different_project(self):
        names = {p: {c['name'] for c in hive.recommend('write tests for the orders', self.project(p), chain=self.col)['stack']}
                 for p in ('dotnet', 'ios', 'ml', 'quarkus')}
        self.assertIn('csharp-testing', names['dotnet'])
        self.assertIn('swift-protocol-di-testing', names['ios'])
        self.assertIn('python-testing', names['ml'])
        for p in ('ios', 'ml', 'quarkus'):
            self.assertNotIn('csharp-testing', names[p])

    def test_never_offers_itself(self):
        for task in ('decide which skills to use', 'manage skills for this task', 'sfp manager'):
            names = {c['name'] for c in hive.recommend(task, chain=self.col)['stack']}
            self.assertFalse(names & {'sfp', 'sfp-manager'}, task)

    def test_empty_for_filler(self):
        self.assertEqual(hive.recommend('for the of a', chain=self.col)['stack'], [])

    def test_every_member_explains_itself(self):
        res = hive.recommend('add a module for refunds', self.project('nestjs'), chain=self.col)
        self.assertTrue(res['stack'])
        for c in res['stack']:
            self.assertTrue(any(r.startswith('backed by:') for r in c['reasons']))
            self.assertTrue(os.path.isfile(os.path.join(ROOT, c['path'])))
        self.assertIn('colony', res)

    def test_project_scan_is_cached(self):
        p = self.project('rails')
        hive._SCANS.pop(os.path.abspath(p), None)
        first = hive.scan(p)
        self.assertIs(hive.scan(p), first)

    def test_fast(self):
        res = hive.recommend('roll out the new version without downtime', self.project('infra'), chain=self.col)
        self.assertLess(res['ms'], 500)


class LearningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ['SFP_USAGE_LOG'] = os.path.join(self.tmp.name, 'usage.jsonl')
        os.environ.pop('SFP_NO_USAGE_LOG', None)

    def tearDown(self):
        os.environ.pop('SFP_USAGE_LOG', None)
        self.tmp.cleanup()

    def test_rows_are_distributions(self):
        col = hive.colony()
        for a in ('api-design', 'career-ops', 'swiftui-patterns'):
            self.assertAlmostEqual(sum(col.prob(a, b) for b in core.SKILLS), 1.0, places=6)

    def test_outcomes_move_thresholds_and_choices(self):
        task = 'write tests for the checkout form'
        before = [c['name'] for c in hive.recommend(task, chain=hive.colony())['stack']]
        for _ in range(5):
            v1.record('e2e-testing', 'helped')
        col = hive.colony()
        self.assertLess(col.threshold_scale('e2e-testing'), 1.0)
        after = [c['name'] for c in hive.recommend(task, chain=col)['stack']]
        self.assertNotIn('e2e-testing', before)
        self.assertIn('e2e-testing', after)
        for _ in range(5):
            v1.record('cpp-testing', 'unhelpful')
        self.assertGreater(hive.colony().threshold_scale('cpp-testing'), 1.0)

    def test_trails_evaporate(self):
        now = time.time()
        old = [{'t': now - 120 * 86400, 'skill': 'golang-testing', 'session': 'old'},
               {'t': now - 120 * 86400, 'skill': 'docker-patterns', 'session': 'old'}]
        new = [{'t': now, 'skill': 'golang-testing', 'session': 'new'},
               {'t': now, 'skill': 'canary-watch', 'session': 'new'}]
        col = hive.Colony(v1.RECIPES, old + new, now=now)
        self.assertGreater(col.prob('golang-testing', 'canary-watch'), col.prob('golang-testing', 'docker-patterns'))
        # A four-month-old trail is worth about 1/16 of a new one.
        self.assertAlmostEqual(col.c['golang-testing']['docker-patterns'], 2 ** -4, places=3)

    def test_recorded_trail_becomes_the_prediction(self):
        for i in range(3):
            v1.record('golang-testing', session='s%d' % i)
            v1.record('canary-watch', session='s%d' % i)
        self.assertEqual(hive.colony().next('golang-testing', 1)[0][1], 'canary-watch')


class QualityTest(unittest.TestCase):
    """The README quotes these figures; a change that makes the hive worse fails here."""

    @classmethod
    def setUpClass(cls):
        cls.ev = hive.evaluate(os.path.join(ROOT, 'tests'))

    def test_at_least_as_good_as_v1_and_search_everywhere(self):
        for key in ('bench', 'proj', 'fresh'):
            self.assertGreaterEqual(self.ev[key + '_hive']['hit'], self.ev[key + '_v1']['hit'], key)
            self.assertGreaterEqual(self.ev[key + '_hive']['hit'], self.ev[key + '_search']['hit'], key)

    def test_floors(self):
        self.assertGreaterEqual(self.ev['bench_hive']['hit'], 0.85)
        self.assertGreaterEqual(self.ev['proj_hive']['hit'], 0.75)
        self.assertGreaterEqual(self.ev['fresh_hive']['hit'], 0.80)
        self.assertGreaterEqual(self.ev['bench_hive']['first'], 0.75)

    def test_never_the_wrong_technology(self):
        for key in ('bench', 'proj', 'fresh'):
            self.assertEqual(self.ev[key + '_hive']['wrong'], 0, key)

    def test_stacks_stay_small(self):
        for key in ('bench', 'proj', 'fresh'):
            self.assertLessEqual(self.ev[key + '_hive']['size'], 2.6, key)


class InterfaceTest(unittest.TestCase):
    def test_skill_launcher_runs_the_hive(self):
        script = os.path.join(ROOT, 'templates', 'sfp-manager', 'scripts', 'stack.py')
        done = subprocess.run([sys.executable, '-I', script, 'recommend', 'write table driven tests in Go', '--json'],
                              capture_output=True, text=True, env=dict(os.environ, SFP_ROOT=ROOT), timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        res = json.loads(done.stdout)
        self.assertTrue(res['engine'].startswith('hive'))
        self.assertIn('golang-testing', [c['name'] for c in res['stack']])

    def test_v1_is_still_available(self):
        script = os.path.join(ROOT, 'mcp', 'sfp_hive.py')
        done = subprocess.run([sys.executable, '-I', script, 'recommend', 'write tests', '--engine', 'v1', '--json'],
                              capture_output=True, text=True, env=dict(os.environ, SFP_ROOT=ROOT), timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn('engine', json.loads(done.stdout))


if __name__ == '__main__':
    unittest.main()
