"""Attaching skills while typing (mcp/sfp_live.py): waits for enough words, stays steady, respects pins and removals,
and only logs when the message is sent.

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

import sfp_live as lv  # noqa: E402

DEPLOY = 'add a dockerfile and deploy this service to kubernetes'
FORM = 'make the login form accessible and animate the button'


class LiveTest(unittest.TestCase):
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

    def names(self, r):
        return [a['name'] for a in r['attached']]

    def test_waits_until_there_are_enough_words(self):
        r = lv.live('fix')
        self.assertEqual((r['status'], r['attached'], r['changed']), ('waiting', [], False))

    def test_typing_more_of_the_same_thing_keeps_the_skills(self):
        first = lv.live(DEPLOY)
        self.assertEqual(first['status'], 'updated')
        self.assertTrue(first['attached'])
        again = lv.live(DEPLOY + ' on friday', first['state'])
        self.assertEqual(again['status'], 'kept')
        self.assertFalse(again['changed'])
        self.assertEqual(self.names(again), self.names(first))

    def test_a_new_topic_chooses_again(self):
        first = lv.live(DEPLOY)
        second = lv.live(FORM, first['state'])
        self.assertEqual(second['status'], 'updated')
        self.assertTrue(second['changed'])
        self.assertNotEqual(self.names(second), self.names(first))

    def test_pins_stay_and_removals_never_return(self):
        r = lv.live(FORM, pin=['docker-patterns'])
        self.assertEqual(r['attached'][0]['name'], 'docker-patterns')
        self.assertEqual(r['attached'][0]['source'], 'pinned')
        gone = self.names(r)[1]
        r2 = lv.live(FORM, r['state'], remove=[gone])
        self.assertNotIn(gone, self.names(r2))
        r3 = lv.live(FORM + ' please', r2['state'])
        self.assertNotIn(gone, self.names(r3))
        r4 = lv.live(FORM, r3['state'], restore=[gone], unpin=['docker-patterns'])
        self.assertNotIn('docker-patterns', self.names(r4))

    def test_never_more_than_the_limit(self):
        r = lv.live(FORM, max_skills=2, pin=['docker-patterns'])
        self.assertLessEqual(len(r['attached']), 2)

    def test_a_pinned_skill_cannot_also_be_removed(self):
        r = lv.live(FORM, pin=['docker-patterns'], remove=['docker-patterns'])
        self.assertNotIn('docker-patterns', self.names(r))

    def test_typing_logs_nothing_and_sending_logs_one_decision(self):
        log = os.path.join(self.tmp.name, 'decisions.jsonl')
        r = lv.live(DEPLOY)
        lv.live(DEPLOY + ' now', r['state'])
        self.assertFalse(os.path.exists(log))
        sent = lv.live(DEPLOY, r['state'], commit=True)
        self.assertEqual(sent['status'], 'committed')
        self.assertTrue(sent['decision'])
        with open(log) as f:
            self.assertEqual(len(f.read().splitlines()), 1)

    def test_the_command_line(self):
        hive = os.path.join(ROOT, 'mcp', 'sfp_hive.py')
        out = subprocess.run([sys.executable, hive, 'live', FORM, '--json'], capture_output=True, text=True, timeout=60,
                             env=dict(os.environ))
        self.assertEqual(out.returncode, 0, out.stderr)
        res = json.loads(out.stdout)
        out2 = subprocess.run([sys.executable, hive, 'live', FORM + ' now', '--json', '--state', json.dumps(res['state'])],
                              capture_output=True, text=True, timeout=60, env=dict(os.environ))
        self.assertEqual(json.loads(out2.stdout)['status'], 'kept')


if __name__ == '__main__':
    unittest.main()
