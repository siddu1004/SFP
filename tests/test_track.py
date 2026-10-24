"""The activity tracker (mcp/sfp_track.py): evidence from events, the Kalman phase filter, the Markov chain of
phases, and the `track` command that ties them to the hive.

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

import sfp_hive as sel  # noqa: E402
import sfp_track as trk  # noqa: E402


def load(name):
    with open(os.path.join(ROOT, 'tests', name), encoding='utf-8') as f:
        return json.load(f)['sessions']


def top(ev):
    return max(ev, key=ev.get)


class EvidenceTest(unittest.TestCase):
    def test_files_and_commands_point_at_the_right_phase(self):
        for event, phase in (({'kind': 'save', 'path': 'pkg/parse_test.go'}, 'test'),
                             ({'kind': 'save', 'path': 'src/Button.spec.tsx'}, 'test'),
                             ({'kind': 'save', 'path': 'Dockerfile'}, 'ship'),
                             ({'kind': 'save', 'path': '.github/workflows/ci.yml'}, 'ship'),
                             ({'kind': 'save', 'path': 'docs/guide.md'}, 'document'),
                             ({'kind': 'save', 'path': 'src/app.py'}, 'build'),
                             ({'kind': 'run', 'command': 'pytest -q'}, 'test'),
                             ({'kind': 'run', 'command': 'npm audit'}, 'secure'),
                             ({'kind': 'run', 'command': 'git push origin main'}, 'ship'),
                             ({'kind': 'run', 'command': 'hyperfine ./bench'}, 'optimize'),
                             ({'kind': 'prompt', 'text': 'review this pull request'}, 'review')):
            self.assertEqual(top(trk.evidence(event)[0]), phase, event)

    def test_a_failure_turns_the_next_edits_into_debugging_until_something_passes(self):
        ctx = {}
        self.assertEqual(top(trk.evidence({'kind': 'save', 'path': 'a.py'}, ctx)[0]), 'build')
        trk.evidence({'kind': 'run', 'command': 'pytest', 'exit': 1}, ctx)
        self.assertEqual(top(trk.evidence({'kind': 'save', 'path': 'a.py'}, ctx)[0]), 'debug')
        trk.evidence({'kind': 'run', 'command': 'pytest', 'exit': 0}, ctx)
        self.assertEqual(top(trk.evidence({'kind': 'save', 'path': 'a.py'}, ctx)[0]), 'build')

    def test_an_event_with_nothing_to_say_gives_no_evidence(self):
        self.assertEqual(sum(trk.evidence({'kind': 'open', 'path': 'notes.txt'})[0].values()), 0)


class FilterTest(unittest.TestCase):
    def test_evidence_raises_a_phase_and_quiet_lets_it_relax(self):
        f = trk.PhaseFilter()
        f.predict(0)
        f.update({**{p: 0 for p in trk.PHASES}, 'test': 2.0})
        high = f.x['test']
        self.assertGreater(high, trk.PRIOR)
        f.predict(3 * trk.RELAX_SECONDS)
        self.assertLess(abs(f.x['test'] - trk.PRIOR), abs(high - trk.PRIOR) / 5)

    def test_confidence_grows_with_evidence_and_falls_with_time(self):
        f = trk.PhaseFilter()
        f.predict(0)
        before = f.confidence('test')
        for i in range(4):
            f.predict(i * 30)
            f.update({**{p: 0 for p in trk.PHASES}, 'test': 1.4})
        self.assertGreater(f.confidence('test'), before)
        sure = f.confidence('test')
        f.predict(4 * 30 + 3600)
        self.assertLess(f.confidence('test'), sure)

    def test_one_stray_event_does_not_switch_the_phase(self):
        build = [{'t': i * 30, 'kind': 'save', 'path': 'src/a%d.py' % i} for i in range(6)]
        stray = [{'t': 200, 'kind': 'open', 'path': 'README.md'}]
        state, _f, _c, changes = trk.run(build + stray)
        self.assertEqual(state['current'], 'build')
        self.assertEqual(changes, [])

    def test_a_sustained_change_switches_and_is_recorded(self):
        events = [{'t': i * 30, 'kind': 'save', 'path': 'src/a.py'} for i in range(5)]
        events += [{'t': 200 + i * 30, 'kind': 'run', 'command': 'pytest'} for i in range(4)]
        state, _f, chain, changes = trk.run(events)
        self.assertEqual(state['current'], 'test')
        self.assertEqual([(c['from'], c['to']) for c in changes], [('build', 'test')])
        self.assertIn('test', chain.counts['build'])


class ChainTest(unittest.TestCase):
    def test_the_prior_follows_the_usual_order_of_work(self):
        c = trk.PhaseChain(now=0)
        self.assertEqual(c.next('build')[0][0], 'test')
        self.assertIn(c.next('test')[0][0], ('debug', 'build', 'review'))
        self.assertNotIn('build', [p for p, _ in c.next('build')])
        self.assertAlmostEqual(sum(p for _, p in c.next('plan')), 1.0, places=6)

    def test_what_is_learned_overrides_the_prior_and_fades(self):
        c = trk.PhaseChain(now=0)
        for _ in range(6):
            c.record('build', 'document', 0)
        self.assertEqual(c.next('build')[0][0], 'document')
        later = trk.PhaseChain(c.counts, now=200 * 86400)
        self.assertEqual(later.next('build')[0][0], 'test')


class QualityTest(unittest.TestCase):
    """Floors from tests/track_sessions.json (the dev set the filter was tuned on) and tests/track_heldout.json
    (written before the tuning). The numbers are in docs/TRACKING.md, including where the filter loses."""

    def test_dev_set(self):
        r = trk.evaluate(load('track_sessions.json'))
        self.assertGreaterEqual(r['kalman']['accuracy'], 0.78)
        self.assertLess(r['kalman']['switches'], r['last']['switches'])

    def test_heldout_set_is_stable_and_reasonable(self):
        r = trk.evaluate(load('track_heldout.json'))
        self.assertGreaterEqual(r['kalman']['accuracy'], 0.6)
        self.assertLessEqual(r['kalman']['switches'], r['last']['switches'])


class HiveTest(unittest.TestCase):
    def test_a_phase_hint_steers_the_hive(self):
        plain = sel.select('the orders module', history=sel.History(sel.v1.RECIPES, []))
        hinted = sel.select('the orders module', history=sel.History(sel.v1.RECIPES, []), phase_hint={'test': 1.0})
        self.assertTrue(any(c['phase'] == 'test' for c in hinted['stack']), hinted['stack'])
        self.assertNotEqual([c['name'] for c in plain['stack']], [c['name'] for c in hinted['stack']])

    def test_the_track_command_round_trip(self):
        with tempfile.TemporaryDirectory() as data:
            env = dict(os.environ, SFP_DATA_DIR=data)
            env.pop('SFP_NO_USAGE_LOG', None)
            events = [{'t': 1000 + i * 30, 'kind': 'run', 'command': 'go test ./...', 'exit': 0} for i in range(4)]
            done = subprocess.run([sys.executable, os.path.join(ROOT, 'mcp', 'sfp_hive.py'), 'track', '--json'],
                                  input=json.dumps(events), capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(done.returncode, 0, done.stderr)
            res = json.loads(done.stdout)
            self.assertEqual(res['phase'], 'test')
            self.assertEqual(res['layer'], 'check')
            self.assertTrue(res['skills'])
            self.assertTrue(res['next'])
            self.assertTrue(os.path.isfile(os.path.join(data, 'track_state.json')))
            # The state carries over: a later batch continues from it.
            more = [{'t': 2000 + i * 30, 'kind': 'save', 'path': 'Dockerfile'} for i in range(5)]
            again = subprocess.run([sys.executable, os.path.join(ROOT, 'mcp', 'sfp_hive.py'), 'track', '--json', '--no-select'],
                                   input=json.dumps(more), capture_output=True, text=True, env=env, timeout=120)
            res2 = json.loads(again.stdout)
            self.assertEqual(res2['phase'], 'ship')
            self.assertEqual(res2['changes'][-1]['from'], 'test')


if __name__ == '__main__':
    unittest.main()
