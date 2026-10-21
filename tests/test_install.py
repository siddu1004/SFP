"""The installer (scripts/install.py): upgrading from the old skill name, and running an installed skill.

Everything runs against a throwaway home folder; the real one is never touched.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(ROOT, 'scripts', 'install.py')


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, 'home')
        os.makedirs(os.path.join(self.home, '.cursor'))
        self.skills = os.path.join(self.home, '.cursor', 'skills')
        self.env = dict(os.environ, HOME=self.home, USERPROFILE=self.home)
        for k in ('SFP_USAGE_LOG', 'SFP_NO_LEARNING', 'SFP_NO_USAGE_LOG', 'SFP_LEARN_WORDS', 'SFP_DATA_DIR', 'SFP_ROOT'):
            self.env.pop(k, None)

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, *args):
        return subprocess.run([sys.executable, '-I', INSTALL, 'install', '--tools', 'cursor'] + list(args),
                              capture_output=True, text=True, env=self.env, timeout=120)

    def test_installs_the_router_and_the_selector(self):
        done = self.install('--categories', 'sfp')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(sorted(os.listdir(self.skills)), ['sfp', 'sfp-hive'])
        self.assertTrue(os.path.isfile(os.path.join(self.skills, 'sfp-hive', 'scripts', 'select_skills.py')))

    def test_an_old_sfp_manager_folder_that_sfp_made_is_replaced(self):
        old = os.path.join(self.skills, 'sfp-manager')
        os.makedirs(old)
        with open(os.path.join(old, 'SKILL.md'), 'w') as f:
            f.write('---\nname: sfp-manager\n---\n')
        with open(os.path.join(old, '.sfp'), 'w') as f:      # the marker the installer leaves
            f.write('sfp\n')
        done = self.install('--categories', 'sfp')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(os.path.exists(old))
        self.assertIn('sfp-hive', os.listdir(self.skills))
        self.assertIn('renamed to sfp-hive', done.stdout)

    def test_a_3_0_sfp_select_folder_that_sfp_made_is_replaced(self):
        old = os.path.join(self.skills, 'sfp-select')
        os.makedirs(old)
        with open(os.path.join(old, '.sfp'), 'w') as f:
            f.write('sfp\n')
        self.assertEqual(self.install('--categories', 'sfp').returncode, 0)
        self.assertFalse(os.path.exists(old))
        self.assertEqual(sorted(os.listdir(self.skills)), ['sfp', 'sfp-hive'])

    def test_a_folder_with_that_name_that_the_user_made_is_left_alone(self):
        mine = os.path.join(self.skills, 'sfp-manager')
        os.makedirs(mine)
        with open(os.path.join(mine, 'SKILL.md'), 'w') as f:
            f.write('---\nname: sfp-manager\n---\nmy own\n')
        self.assertEqual(self.install('--categories', 'sfp').returncode, 0)
        self.assertTrue(os.path.isfile(os.path.join(mine, 'SKILL.md')))

    def test_the_installed_selector_runs_from_where_it_was_installed(self):
        self.assertEqual(self.install('--categories', 'sfp').returncode, 0)
        script = os.path.join(self.skills, 'sfp-hive', 'scripts', 'select_skills.py')
        project = os.path.join(self.tmp.name, 'proj')
        os.makedirs(project)
        with open(os.path.join(project, 'go.mod'), 'w') as f:
            f.write('module example.com/x\n')
        env = dict(self.env)   # HOME is the throwaway one, so the learning data goes there too
        done = subprocess.run([sys.executable, '-I', script, 'select', 'write table driven tests', '--project', project, '--json'],
                              capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        res = json.loads(done.stdout)
        self.assertIn('golang-testing', [c['name'] for c in res['stack']])
        fb = subprocess.run([sys.executable, '-I', script, 'feedback', res['decision'], '--helped', 'golang-testing'],
                            capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(fb.returncode, 0, fb.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.home, '.sfp', 'decisions.jsonl')))
        self.assertTrue(os.path.isfile(os.path.join(self.home, '.sfp', 'feedback.jsonl')))

    def test_uninstall_removes_the_selector_too(self):
        self.install('--categories', 'sfp')
        done = subprocess.run([sys.executable, '-I', INSTALL, 'uninstall', '--tools', 'cursor'], capture_output=True, text=True,
                              env=self.env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(os.listdir(self.skills) if os.path.isdir(self.skills) else [], [])


if __name__ == '__main__':
    unittest.main()
