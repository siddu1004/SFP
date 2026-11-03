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

    def test_update_command_runs_successfully(self):
        done = self.install('--categories', 'sfp')
        self.assertEqual(done.returncode, 0, done.stderr)
        update_done = subprocess.run([sys.executable, '-I', INSTALL, 'update', '--tools', 'cursor', '--categories', 'sfp'],
                                     capture_output=True, text=True, env=self.env, timeout=120)
        self.assertEqual(update_done.returncode, 0, update_done.stderr)
        self.assertIn('Refreshing installed skills', update_done.stdout)
        self.assertIn('Update complete', update_done.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.skills, 'sfp')))


class VSCodeAndRulesTest(InstallerTest):
    """VS Code reads Copilot's skills folders and has its own mcp.json; `rules` writes a removable standing instruction."""

    def run_install(self, *args):
        return subprocess.run([sys.executable, '-I', INSTALL] + list(args), capture_output=True, text=True, env=self.env, timeout=120)

    def test_vscode_is_the_copilot_skills_folder(self):
        project = os.path.join(self.tmp.name, 'proj')
        os.makedirs(project)
        done = self.run_install('install', '--tools', 'vscode', '--categories', 'sfp', '--project', project)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(sorted(os.listdir(os.path.join(project, '.github', 'skills'))), ['sfp', 'sfp-hive'])

    def test_vscode_mcp_uses_the_servers_key_and_keeps_other_servers(self):
        project = os.path.join(self.tmp.name, 'proj')
        os.makedirs(os.path.join(project, '.vscode'))
        path = os.path.join(project, '.vscode', 'mcp.json')
        with open(path, 'w') as f:
            json.dump({'servers': {'other': {'command': 'x'}}, 'inputs': []}, f)
        self.assertEqual(self.run_install('mcp', '--tools', 'vscode', '--project', project).returncode, 0)
        with open(path) as f:
            cfg = json.load(f)
        self.assertEqual(cfg['servers']['sfp']['type'], 'stdio')
        self.assertIn('other', cfg['servers'])
        self.assertNotIn('mcpServers', cfg)
        self.run_install('mcp', '--tools', 'vscode', '--project', project, '--remove')
        with open(path) as f:
            self.assertEqual(list(json.load(f)['servers']), ['other'])

    def test_rules_keep_the_users_text_and_come_out_cleanly(self):
        project = os.path.join(self.tmp.name, 'proj')
        os.makedirs(project)
        path = os.path.join(project, 'AGENTS.md')
        with open(path, 'w') as f:
            f.write('# Mine\n\nkeep this\n')
        self.run_install('rules', '--tools', 'codex', '--project', project)
        self.run_install('rules', '--tools', 'codex', '--project', project)   # twice: still one block
        with open(path) as f:
            text = f.read()
        self.assertEqual(text.count('<!-- sfp:start -->'), 1)
        self.assertTrue(text.startswith('# Mine\n\nkeep this\n'))
        self.assertIn('select_skills', text)
        self.run_install('rules', '--tools', 'codex', '--project', project, '--remove')
        with open(path) as f:
            self.assertEqual(f.read(), '# Mine\n\nkeep this\n')

    def test_rules_in_a_file_that_held_only_our_block_remove_the_file(self):
        project = os.path.join(self.tmp.name, 'proj')
        os.makedirs(project)
        self.run_install('rules', '--tools', 'claude', '--project', project)
        self.assertTrue(os.path.isfile(os.path.join(project, 'CLAUDE.md')))
        self.run_install('rules', '--tools', 'claude', '--project', project, '--remove')
        self.assertFalse(os.path.exists(os.path.join(project, 'CLAUDE.md')))

    def test_antigravity_and_multi_ide_support(self):
        cfg_dir = os.path.join(self.home, '.gemini', 'config')
        os.makedirs(cfg_dir, exist_ok=True)
        done = self.run_install('install', '--tools', 'antigravity-ide', '--categories', 'sfp,agent-dev')
        self.assertEqual(done.returncode, 0, done.stderr)
        ag_skills = os.path.join(cfg_dir, 'skills')
        self.assertTrue(os.path.isdir(os.path.join(ag_skills, 'sfp')))
        self.assertTrue(os.path.isdir(os.path.join(ag_skills, 'sfp-hive')))
        # Core skills (sfp, sfp-hive) must have newer or equal mtime than other installed skills
        sfp_mtime = os.path.getmtime(os.path.join(ag_skills, 'sfp', 'SKILL.md'))
        other_mtime = os.path.getmtime(os.path.join(ag_skills, 'investigate-first', 'SKILL.md'))
        self.assertGreaterEqual(sfp_mtime, other_mtime)
        # Antigravity plugin installed and enabled in ~/.gemini/config/config.json
        self.assertTrue(os.path.isfile(os.path.join(cfg_dir, 'plugins', 'sfp', 'plugin.json')))
        with open(os.path.join(cfg_dir, 'config.json'), encoding='utf-8') as f:
            self.assertEqual(json.load(f)['plugins']['sfp'], {'enabled': True})
        # Antigravity MCP registration
        mcp_done = self.run_install('mcp', '--tools', 'antigravity')
        self.assertEqual(mcp_done.returncode, 0, mcp_done.stderr)
        with open(os.path.join(cfg_dir, 'mcp_config.json'), encoding='utf-8') as f:
            mcp_cfg = json.load(f)
        self.assertIn('sfp', mcp_cfg['mcpServers'])
        # Antigravity user-level rules
        rules_done = self.run_install('rules', '--tools', 'antigravity')
        self.assertEqual(rules_done.returncode, 0, rules_done.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.home, '.gemini', 'GEMINI.md')))

    def test_latest_release_tag_pins_to_highest_semver_tag(self):
        import subprocess
        from unittest.mock import patch
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        import install
        
        # Test semver parsing and ordering
        fake_output = "v3.2.0\nv3.17.3\nv3.18.0\nv3.17.7\nbeta-v4.0\n"
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.stdout = fake_output
            mock_run.return_value.returncode = 0
            tag = install.latest_release_tag(ROOT)
            self.assertEqual(tag, 'v3.18.0')

    def test_update_pins_to_release_tag_and_never_pulls_main(self):
        from unittest.mock import patch
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        import install
        
        calls = []
        def fake_run(cmd, *a, **kw):
            calls.append(cmd)
            res = unittest.mock.MagicMock()
            res.returncode = 0
            res.stdout = "v3.18.0\nv3.17.7\n" if 'tag' in cmd else ""
            res.stderr = ""
            return res

        with patch('subprocess.run', side_effect=fake_run), patch('install.cmd_install'):
            args = unittest.mock.MagicMock()
            cat = {'skills': []}
            install.cmd_update(cat, args)
            
            # Verify fetch was called with --tags
            self.assertTrue(any('fetch' in c and '--tags' in c for c in calls))
            # Verify checkout was called with the latest tag
            self.assertTrue(any('checkout' in c and 'v3.18.0' in c for c in calls))
            # Critical requirement: MUST NEVER pull main
            for c in calls:
                self.assertFalse('pull' in c and 'main' in c, f"Command pulled main: {c}")


if __name__ == '__main__':
    unittest.main()
