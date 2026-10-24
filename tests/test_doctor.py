"""`sfp_hive.py doctor` (mcp/sfp_doctor.py): every part of the hive is checked, a clean setup has no failures, and a
missing router is a warning with the command that fixes it, not a failure.

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

import sfp_doctor as dr  # noqa: E402


class DoctorTest(unittest.TestCase):
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

    def test_every_part_is_checked_and_a_clean_setup_does_not_fail(self):
        items = dr.checks(router_port=1)
        names = {c['name'] for c in items}
        for want in ('Catalog', 'Search index', 'Selection', 'Live attaching', 'Needs', 'Skill library', 'Router running', 'MCP server'):
            self.assertIn(want, names)
        self.assertNotEqual(dr.summary(items), 'fail', dr.format_checks(items))
        for c in items:
            self.assertIn(c['status'], ('ok', 'warn', 'fail'))
            if c['status'] != 'ok':
                self.assertTrue(c['fix'] or c['detail'], c['name'])

    def test_a_router_that_is_not_running_is_a_warning_with_the_fix(self):
        c = next(c for c in dr.checks(router_port=1) if c['name'] == 'Router running')
        self.assertEqual(c['status'], 'warn')
        self.assertIn('sfp_route.py serve', c['fix'])

    def test_the_command_line_gives_json_and_an_exit_code(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, 'mcp', 'sfp_hive.py'), 'doctor', '--json', '--port', '1'],
                             capture_output=True, text=True, timeout=120, env=dict(os.environ))
        self.assertEqual(out.returncode, 0, out.stderr)
        res = json.loads(out.stdout)
        self.assertIn(res['status'], ('ok', 'warn'))
        self.assertGreaterEqual(len(res['checks']), 10)


if __name__ == '__main__':
    unittest.main()
