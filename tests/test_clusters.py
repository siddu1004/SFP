"""Skill clusters (mcp/sfp_clusters.py and clusters.json): every skill has one home, clusters are named and
not empty, your own clusters can be added and removed, and usage is counted from the hive's logs.

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

import sfp_clusters as cl  # noqa: E402


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


class SharedClustersTest(DataDir):
    def test_every_skill_has_exactly_one_home_and_no_cluster_is_empty(self):
        res = cl.clusters()
        homes = [s['name'] for c in res for s in c['skills']]
        self.assertEqual(len(homes), len(set(homes)))
        self.assertEqual(set(homes), {s['name'] for s in cl.core.CATALOG['skills']})
        self.assertTrue(all(c['count'] > 0 for c in res))
        self.assertLessEqual(len(res), 60)

    def test_known_skills_land_where_a_person_would_look(self):
        home = {n: ids[0] for n, ids in cl.assign().items()}
        for name, cid in (('react-three-fiber', 'three-d-web'), ('gsd-ship', 'gsd'), ('frontend-a11y', 'accessibility'),
                          ('fastapi-patterns', 'backend'), ('golang-testing', 'testing'), ('cli-setup', 'gateway'),
                          ('sfp-hive', 'sfp'), ('postgres-patterns', 'databases')):
            if name in home:
                self.assertEqual(home[name], cid, name)

    def test_every_rule_has_an_id_a_name_and_a_valid_pattern(self):
        import re
        ids = set()
        for r in cl.shared_rules():
            self.assertTrue(r['id'] and r['name'])
            self.assertNotIn(r['id'], ids)
            ids.add(r['id'])
            if r.get('name_rx'):
                re.compile(r['name_rx'])


class UserClustersTest(DataDir):
    def test_add_list_and_remove_a_cluster_of_your_own(self):
        cl.add_user_cluster('My UI kit', ['impeccable', 'frontend-a11y'], 'what I use for pages')
        mine = [c for c in cl.clusters() if c['mine']]
        self.assertEqual(len(mine), 1)
        self.assertEqual([s['name'] for s in mine[0]['skills']], ['impeccable', 'frontend-a11y'])
        cl.add_user_cluster('My UI kit', ['impeccable'])   # replaces
        self.assertEqual([s['name'] for s in [c for c in cl.clusters() if c['mine']][0]['skills']], ['impeccable'])
        self.assertEqual(cl.remove_user_cluster('My UI kit'), {'removed': 1})
        self.assertFalse([c for c in cl.clusters() if c['mine']])

    def test_an_unknown_skill_is_refused(self):
        with self.assertRaises(SystemExit):
            cl.add_user_cluster('Bad', ['no-such-skill-xyz'])


class UsageTest(DataDir):
    def test_usage_is_counted_from_the_logs(self):
        d = self.tmp.name
        with open(os.path.join(d, 'decisions.jsonl'), 'w') as f:
            f.write(json.dumps({'id': 'd_1', 't': 1, 'stack': ['impeccable', 'frontend-a11y']}) + '\n')
            f.write(json.dumps({'id': 'd_2', 't': 2, 'stack': ['impeccable']}) + '\n')
        with open(os.path.join(d, 'feedback.jsonl'), 'w') as f:
            f.write(json.dumps({'t': 3, 'decision': 'd_1', 'skill': 'impeccable', 'verdict': 'helped'}) + '\n')
        u = cl.usage()
        self.assertEqual(u['impeccable']['chosen'], 2)
        self.assertEqual(u['impeccable']['helped'], 1)
        res = cl.clusters(with_usage=True)
        self.assertGreaterEqual(sum(c['used'] for c in res), 2)

    def test_the_command_line(self):
        env = dict(os.environ)
        hive = os.path.join(ROOT, 'mcp', 'sfp_hive.py')
        out = subprocess.run([sys.executable, hive, 'cluster-add', 'Quick', '--skills', 'impeccable'], capture_output=True,
                             text=True, env=env, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        res = json.loads(subprocess.run([sys.executable, hive, 'clusters', '--json'], capture_output=True, text=True,
                                        env=env, timeout=60).stdout)
        self.assertIn('Quick', [c['name'] for c in res if c['mine']])


if __name__ == '__main__':
    unittest.main()
