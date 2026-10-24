"""Families, the top level of the library (families.json), and the skill detail command: every cluster, skill and
bundle has exactly one family, there are few families, and the detail window has what it shows.

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


class FamiliesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old = os.environ.get('SFP_DATA_DIR')
        os.environ['SFP_DATA_DIR'] = cls.tmp.name
        cls.lib = lib.library()

    @classmethod
    def tearDownClass(cls):
        if cls.old is None:
            os.environ.pop('SFP_DATA_DIR', None)
        else:
            os.environ['SFP_DATA_DIR'] = cls.old
        cls.tmp.cleanup()

    def test_there_are_few_families_and_none_is_empty_or_huge(self):
        fams = self.lib['families']
        self.assertLessEqual(len(fams), 12)
        total = sum(f['count'] for f in fams)
        self.assertEqual(total, self.lib['counts']['skills'])
        for f in fams:
            self.assertGreater(f['count'], 0, f['id'])
            self.assertLessEqual(f['count'], 0.3 * total, f['id'])
            self.assertTrue(f['name'] and f['blurb'] and f['icon'])

    def test_every_cluster_skill_and_bundle_has_exactly_one_family(self):
        ids = {f['id'] for f in self.lib['families']}
        for c in self.lib['clusters']:
            self.assertIn(c['family'], ids | {'mine'}, c['id'])
        in_families = [c for f in self.lib['families'] for c in f['clusters']]
        self.assertEqual(len(in_families), len(set(in_families)))
        for name, s in self.lib['skills'].items():
            self.assertIn(s['family'], ids, name)
        in_bundles = [b for f in self.lib['families'] for b in f['bundles']]
        self.assertEqual(sorted(in_bundles), sorted(b['id'] for b in self.lib['bundles']))

    def test_known_things_land_where_a_person_would_look(self):
        fam = {n: s['family'] for n, s in self.lib['skills'].items()}
        for name, want in (('frontend-a11y', 'design'), ('docker-patterns', 'ship'), ('application-security-testing', 'cyber'),
                           ('golang-testing', 'quality'), ('freellmapi', 'models'), ('gsd-ship', 'project'), ('image-to-3d', 'creative')):
            self.assertEqual(fam[name], want, name)
        by_id = {b['id']: b['family'] for b in self.lib['bundles']}
        for bid, want in (('harden-an-app', 'cyber'), ('keep-going', 'models'), ('accessible-form', 'design'), ('prepare-release', 'ship')):
            self.assertEqual(by_id[bid], want, bid)


class SkillDetailTest(unittest.TestCase):
    def test_detail_has_everything_the_window_shows(self):
        d = lib.skill_detail('frontend-a11y')
        for key in ('name', 'description', 'use_when', 'family', 'cluster', 'purpose', 'also', 'bundles', 'similar', 'tokens', 'path'):
            self.assertIn(key, d)
        self.assertTrue(d['description'])
        self.assertNotIn('\\', d['path'])
        self.assertIn('accessible-form', [b['id'] for b in d['bundles']])
        self.assertNotIn('frontend-a11y', d['similar'])

    def test_an_unknown_skill_is_refused_and_a_name_is_resolved(self):
        with self.assertRaises(KeyError):
            lib.skill_detail('no-such-skill-xyz')
        self.assertEqual(lib.skill_detail('Frontend-A11y')['name'], 'frontend-a11y')

    def test_the_command_line(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, 'mcp', 'sfp_hive.py'), 'skill', 'frontend-a11y', '--json'],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)['name'], 'frontend-a11y')


if __name__ == '__main__':
    unittest.main()
