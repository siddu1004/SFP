"""The skill library (mcp/sfp_library.py, purposes.json, bundles.json): every skill has one purpose, purposes are
assigned with measured accuracy, bundles name real skills, your own bundles can be added and removed, and
`select --bundle` pins a bundle. The payload the editor reads has the shape the interface depends on.

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
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_library as lib  # noqa: E402


def labels(name):
    with open(os.path.join(ROOT, 'tests', name), encoding='utf-8') as f:
        return json.load(f)['labels']


class DataDir(unittest.TestCase):
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


class PurposeTest(DataDir):
    def test_every_skill_has_one_known_purpose_and_no_purpose_dominates(self):
        a = lib.assignments()
        ids = {p['id'] for p in lib.rules()['purposes']}
        self.assertEqual(set(a), set(lib.core.SKILLS))
        self.assertTrue(all(v['purpose'] in ids for v in a.values()))
        self.assertTrue(all(len(v['also']) <= 2 and v['purpose'] not in v['also'] for v in a.values()))
        biggest = max(sum(1 for v in a.values() if v['purpose'] == i) for i in ids)
        self.assertLessEqual(biggest / len(a), 0.25)
        self.assertEqual(len(ids), 15)

    def test_every_cluster_and_phase_the_rules_name_exists(self):
        import sfp_clusters
        r = lib.rules()
        cluster_ids = {c['id'] for c in sfp_clusters.shared_rules()}
        ids = {p['id'] for p in r['purposes']}
        self.assertLessEqual(set(r['cluster_purpose']) - {'sfp'}, cluster_ids | {'sfp'})
        for cid in cluster_ids:
            self.assertIn(cid, r['cluster_purpose'], cid)
        for v in r['cluster_purpose'].values():
            self.assertIn(v['default'] if isinstance(v, dict) else v, ids)
        self.assertEqual(set(r['phase_purpose'].values()) - ids, set())
        for pid, rx in r['name_rx']:
            self.assertIn(pid, ids)
            __import__('re').compile(rx)

    def test_accuracy_floors(self):
        """On 120 hand-labelled skills the rules were tuned on, and 40 held out (labelled before the second round
        of rules). The measured numbers are in docs/LIBRARY.md; one labeller, and some labels are arguable."""
        a = lib.assignments()
        dev, held = labels('purpose_labels.json'), labels('purpose_heldout.json')
        self.assertGreaterEqual(sum(a[n]['purpose'] == p for n, p in dev.items()) / len(dev), 0.80)
        self.assertGreaterEqual(sum(a[n]['purpose'] == p for n, p in held.items()) / len(held), 0.70)

    def test_labels_name_real_skills_and_real_purposes(self):
        ids = {p['id'] for p in lib.rules()['purposes']}
        for f in ('purpose_labels.json', 'purpose_heldout.json'):
            for n, p in labels(f).items():
                self.assertIn(n, lib.core.SKILLS, n)
                self.assertIn(p, ids, n)
        self.assertFalse(set(labels('purpose_labels.json')) & set(labels('purpose_heldout.json')))


class BundleTest(DataDir):
    def test_shared_bundles_name_real_skills_and_purposes(self):
        ids = {p['id'] for p in lib.rules()['purposes']}
        raw = json.load(open(os.path.join(ROOT, 'bundles.json'), encoding='utf-8'))['bundles']
        got = lib.bundles()
        self.assertEqual(len(got), len(raw))
        seen = set()
        for b in got:
            self.assertNotIn(b['id'], seen)
            seen.add(b['id'])
            self.assertIn(b['purpose'], ids, b['id'])
            self.assertTrue(b['name'] and b['goal'] and b['when'], b['id'])
            self.assertGreaterEqual(len(b['skills']), 2, b['id'])
            self.assertTrue(all(s in lib.core.SKILLS for s in b['skills']), b['id'])
            self.assertEqual(len(b['skills']), len(set(b['skills'])), b['id'])
        for b in raw:
            for s in b.get('skills', []):
                self.assertIn(s, lib.core.SKILLS, s)

    def test_recipe_bundles_follow_the_recipes(self):
        by_id = {b['id']: b for b in lib.bundles()}
        for r in lib.v1.RECIPES:
            if r['name'] in by_id:
                self.assertEqual(by_id[r['name']]['skills'], list(r['skills']))
        self.assertIn('ship-a-page', by_id)

    def test_add_find_and_remove_your_own_bundle(self):
        got = lib.add_user_bundle('My page kit', ['impeccable', 'frontend-a11y'], 'what I use', 'design')
        self.assertEqual(got['id'], 'mine-my-page-kit')
        b = lib.find_bundle('mine-my-page-kit')
        self.assertTrue(b['mine'])
        self.assertEqual(b['skills'], ['impeccable', 'frontend-a11y'])
        self.assertEqual(lib.find_bundle('MY PAGE KIT')['id'], 'mine-my-page-kit')
        lib.add_user_bundle('My page kit', ['impeccable'], purpose='design')   # replaces
        self.assertEqual(lib.find_bundle('my-page-kit' if False else 'mine-my-page-kit')['skills'], ['impeccable'])
        self.assertEqual(lib.remove_user_bundle('My page kit'), {'removed': 1})
        self.assertIsNone(lib.find_bundle('mine-my-page-kit'))

    def test_bad_input_is_refused(self):
        with self.assertRaises(SystemExit):
            lib.add_user_bundle('Bad', ['no-such-skill-xyz'])
        with self.assertRaises(SystemExit):
            lib.add_user_bundle('Empty', [])
        with self.assertRaises(SystemExit):
            lib.add_user_bundle('Odd', ['impeccable'], purpose='nonsense')

    def test_a_bundle_whose_skill_was_removed_is_shown_without_it(self):
        path = lib._user_bundles_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump({'bundles': [{'name': 'Old', 'skills': ['impeccable', 'a-skill-that-is-gone'], 'purpose': 'design'}]}, f)
        self.assertEqual(lib.find_bundle('mine-old')['skills'], ['impeccable'])


class PayloadTest(DataDir):
    def test_the_payload_has_what_the_interface_reads(self):
        t = time.time()
        p = lib.library()
        self.assertLess(time.time() - t, 1.5)
        self.assertEqual(p['counts']['skills'], len(lib.core.SKILLS))
        self.assertEqual(set(p['skills']), set(lib.core.SKILLS))
        self.assertEqual(sum(x['count'] for x in p['purposes']), len(p['skills']))
        self.assertEqual(sum(c['count'] for c in p['clusters']), len(p['skills']))
        for name, row in list(p['skills'].items())[:50]:
            for key in ('d', 'category', 'cluster', 'purpose', 'also', 'n', 't'):
                self.assertIn(key, row, name)
            self.assertLessEqual(len(row['d']), 180)
        ids = {c['id'] for c in p['clusters']}
        self.assertTrue(all(row['cluster'] in ids for row in p['skills'].values()))
        self.assertTrue(p['bundles'])
        json.dumps(p)

    def test_usage_shows_up_in_the_payload(self):
        with open(os.path.join(self.tmp.name, 'decisions.jsonl'), 'w') as f:
            f.write(json.dumps({'id': 'd_1', 't': 1, 'stack': ['impeccable']}) + '\n')
        p = lib.library()
        self.assertEqual(p['skills']['impeccable']['usage']['chosen'], 1)
        self.assertNotIn('usage', p['skills']['frontend-a11y'])


class CommandLineTest(DataDir):
    def run_hive(self, *args, **kw):
        env = dict(os.environ, SFP_DATA_DIR=self.tmp.name)
        env.pop('SFP_NO_USAGE_LOG', None)
        return subprocess.run([sys.executable, os.path.join(ROOT, 'mcp', 'sfp_hive.py')] + list(args), capture_output=True,
                              text=True, env=env, timeout=120, **kw)

    def test_select_with_a_bundle_pins_its_skills(self):
        out = self.run_hive('select', 'add a duration parser', '--bundle', 'go-tests', '--json')
        self.assertEqual(out.returncode, 0, out.stderr)
        res = json.loads(out.stdout)
        names = [c['name'] for c in res['stack']]
        self.assertEqual(res['bundle'], {'id': 'go-tests', 'name': 'Table-driven Go tests'})
        for s in ('golang-testing', 'tdd-workflow', 'verification-loop'):
            self.assertIn(s, names)
        pinned = [c['name'] for c in res['stack'] if c['reasons'][0] == 'pinned by you']
        self.assertEqual(set(pinned), {'golang-testing', 'tdd-workflow', 'verification-loop'})
        self.assertTrue(res['decision'])

    def test_an_unknown_bundle_is_an_error(self):
        out = self.run_hive('select', 'anything', '--bundle', 'nope')
        self.assertNotEqual(out.returncode, 0)
        self.assertIn('no bundle', out.stderr)

    def test_library_bundle_add_and_remove_commands(self):
        self.assertEqual(self.run_hive('bundle-add', 'Quick', '--skills', 'impeccable,frontend-a11y', '--purpose', 'design').returncode, 0)
        lib_json = json.loads(self.run_hive('library').stdout)
        self.assertIn('mine-quick', [b['id'] for b in lib_json['bundles']])
        self.assertEqual(json.loads(self.run_hive('bundle-remove', 'Quick').stdout), {'removed': 1})
        listed = self.run_hive('bundles').stdout
        self.assertNotIn('mine-quick', listed)
        self.assertIn('ship-a-page', listed)


if __name__ == '__main__':
    unittest.main()
