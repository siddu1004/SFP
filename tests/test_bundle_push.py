"""The hive pushes whole bundles (sfp_library.match_bundles, sfp_needs.decide/plan_bundles, sfp_live): a task that fits a
bundle gets all of its skills, in order; a task that fits none gets none; and the match is measured on labelled tasks.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_library as lib  # noqa: E402
import sfp_live as lv  # noqa: E402
import sfp_needs as nd  # noqa: E402


def cases(name):
    with open(os.path.join(ROOT, 'tests', name), encoding='utf-8') as f:
        return json.load(f)['cases']


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get('SFP_DATA_DIR')
        os.environ['SFP_DATA_DIR'] = self.tmp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop('SFP_DATA_DIR', None)
        else:
            os.environ['SFP_DATA_DIR'] = self.old
        self.tmp.cleanup()


def measure(cs):
    pos = hit = pushed = false_push = 0
    for c in cs:
        m = nd.plan_bundles(c['task'])
        top = m[0] if m else None
        if c['bundle']:
            pos += 1
            hit += bool(top and top['id'] == c['bundle'])
            pushed += bool(top and top['id'] == c['bundle'] and top['push'])
        elif top and top['push']:
            false_push += 1
    return pos, hit, pushed, false_push


class MatchingTest(Case):
    def test_dev_set(self):
        pos, hit, pushed, false_push = measure(cases('bundle_dev.json'))
        self.assertGreaterEqual(hit / pos, 0.8)
        self.assertGreaterEqual(pushed / pos, 0.65)
        self.assertEqual(false_push, 0)

    def test_held_out_set(self):
        # Written before the matcher was tuned. It found about half of the right bundles and pushed none that were wrong.
        pos, hit, pushed, false_push = measure(cases('bundle_heldout.json'))
        self.assertGreaterEqual(hit / pos, 0.45)
        self.assertEqual(false_push, 0)

    def test_a_task_that_fits_nothing_matches_nothing(self):
        for t in ('write unit tests for the parser', 'rename the user model fields', 'explain how this recursion works'):
            self.assertEqual(nd.plan_bundles(t), [], t)


class PushTest(Case):
    def test_select_attaches_the_whole_bundle_in_its_order_and_says_so(self):
        res = nd.decide('make the signup form accessible', max_skills=4)
        want = next(b for b in lib.bundles() if b['id'] == 'accessible-form')['skills']
        self.assertEqual(res['bundle']['id'], 'accessible-form')
        self.assertTrue(set(want) <= {c['name'] for c in res['stack']})
        self.assertTrue(res['bundles'][0]['applied'])

    def test_suggest_only_preloads_the_rest(self):
        res = nd.decide('make the signup form accessible', bundles='suggest')
        self.assertNotIn('bundle', res)
        self.assertTrue(res['bundles'][0]['push'])
        self.assertFalse(res['bundles'][0]['applied'] and not res['bundles'][0]['missing'] == [])
        for n in res['bundles'][0]['missing']:
            self.assertIn(n, [p['name'] for p in res['preload']])

    def test_off_ignores_bundles_and_a_low_limit_is_respected(self):
        self.assertEqual(nd.decide('make the signup form accessible', bundles='off')['bundles'], [])
        self.assertNotIn('bundle', nd.decide('make the signup form accessible', max_skills=2))

    def test_removed_skills_stay_out_of_a_pushed_bundle(self):
        res = nd.decide('make the signup form accessible', exclude=['ux-writing'])
        self.assertNotIn('ux-writing', [c['name'] for c in res['stack']])

    def test_live_attaches_the_whole_bundle_in_order(self):
        want = next(b for b in lib.bundles() if b['id'] == 'accessible-form')['skills']
        r = lv.live('make the signup form accessible and keyboard friendly')
        self.assertEqual([a['name'] for a in r['attached']][:len(want)], want)
        self.assertEqual(r['bundles'][0]['id'], 'accessible-form')
        r2 = lv.live('make the signup form accessible and keyboard friendly now', r['state'])
        self.assertEqual(r2['status'], 'kept')
        self.assertEqual(r2['bundles'][0]['id'], 'accessible-form')

    def test_a_small_limit_keeps_live_small(self):
        self.assertLessEqual(len(lv.live('make the signup form accessible and keyboard friendly', max_skills=2)['attached']), 2)

    def test_the_command_line(self):
        hive = os.path.join(ROOT, 'mcp', 'sfp_hive.py')
        env = dict(os.environ)
        for mode, expect in (('push', True), ('off', False)):
            out = subprocess.run([sys.executable, hive, 'select', 'make the signup form accessible', '--json', '--bundles', mode],
                                 capture_output=True, text=True, timeout=60, env=env)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual('bundle' in json.loads(out.stdout), expect, mode)


class PhaseBundlesTest(Case):
    def test_a_phase_loads_the_bundles_that_hold_its_skills(self):
        stack = ['golang-testing', 'tdd-workflow']
        got = lib.phase_bundles('test', stack)
        self.assertTrue(got)
        for b in got:
            self.assertTrue(set(b['covered']) <= set(stack) and set(b['covered']) <= set(b['skills']))
            self.assertEqual(sorted(b['covered'] + b['missing']), sorted(b['skills']))
            self.assertGreaterEqual(b['score'], lib.PHASE_MIN)
        self.assertEqual(got[0]['id'], 'go-tests')

    def test_no_overlap_loads_nothing_and_the_limit_holds(self):
        self.assertEqual(lib.phase_bundles('test', ['no-such-skill']), [])
        self.assertLessEqual(len(lib.phase_bundles('test', ['golang-testing', 'tdd-workflow', 'e2e-testing'], limit=1)), 1)

    def test_tracking_reports_loaded_bundles(self):
        import sfp_track
        with open(os.path.join(ROOT, 'tests', 'track_sessions.json'), encoding='utf-8') as f:
            sessions = json.load(f)
        sessions = sessions['sessions'] if isinstance(sessions, dict) and 'sessions' in sessions else sessions
        out = sfp_track.track(sessions[4]['events'], select=True, persist=False)
        self.assertIn('bundles', out)
        self.assertTrue(all(b['covered'] for b in out['bundles']))


if __name__ == '__main__':
    unittest.main()
