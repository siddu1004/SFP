"""Skills that need a program installed carry their own setup (apps/sfp_app.py and apps/apps.json).

The engine is exercised against a throwaway registry; nothing real is installed. The generated skills
are checked for the engine, the entry and the note at the top.

Run:  python3 -m unittest discover -s tests -v
"""
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, 'apps', 'sfp_app.py')
sys.path.insert(0, os.path.join(ROOT, 'apps'))
import sfp_app  # noqa: E402

with open(os.path.join(ROOT, 'apps', 'apps.json'), encoding='utf-8') as _f:
    APPS = json.load(_f)
with open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8') as _f:
    SKILLS = {s['name']: s for s in json.load(_f)['skills']}


class Quiet(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(401)  # a listening service that wants a key still counts as running
        self.end_headers()

    def log_message(self, *a):
        pass


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.marker = os.path.join(self.tmp.name, 'installed')
        self.reg = os.path.join(self.tmp.name, 'app.json')
        self.env = dict(os.environ, SFP_APPS_FILE=self.reg)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, **over):
        app = {
            'name': 'Demo', 'what': 'a demo', 'homepage': 'https://example.com',
            'needs': [{'tool': 'python3'}],
            'installed': {'path': self.marker},
            'install': [{'os': 'any', 'run': [sys.executable, '-c', 'open(%r,"w").write("x")' % self.marker], 'why': 'makes the marker'}],
            'after': ['All done.'],
        }
        app.update(over)
        with open(self.reg, 'w', encoding='utf-8') as f:
            json.dump(app, f)

    def go(self, *args):
        return subprocess.run([sys.executable, ENGINE] + list(args), capture_output=True, text=True, env=self.env, timeout=60)

    def test_install_without_yes_shows_the_plan_and_changes_nothing(self):
        self.write()
        done = self.go('install')
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn('Plan to install Demo', done.stdout)
        self.assertIn('makes the marker', done.stdout)
        self.assertFalse(os.path.exists(self.marker))

    def test_install_with_yes_runs_the_steps_then_says_what_comes_next(self):
        self.write()
        done = self.go('install', '--yes')
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(os.path.exists(self.marker))
        self.assertIn('All done.', done.stdout)
        self.assertEqual(self.go('status').returncode, 0)

    def test_installing_what_is_installed_does_nothing(self):
        self.write()
        open(self.marker, 'w').close()
        done = self.go('install', '--yes')
        self.assertIn('already installed', done.stdout)

    def test_a_missing_requirement_blocks_the_install_even_with_yes(self):
        self.write(needs=[{'tool': 'no-such-tool-xyz', 'label': 'The thing', 'url': 'https://example.com/get'}])
        done = self.go('install', '--yes')
        self.assertEqual(done.returncode, 1)
        self.assertIn('MISSING The thing is not installed: https://example.com/get', done.stdout)
        self.assertFalse(os.path.exists(self.marker))

    def test_a_soft_version_requirement_warns_but_does_not_block(self):
        self.write(needs=[{'tool': 'python3', 'range': [[99, 0, 0], [100, 0, 0]], 'soft': True, 'label': 'Python 99'}])
        done = self.go('install', '--yes')
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn('WARNING Python 99', done.stdout)

    def test_a_failing_step_stops_and_is_reported(self):
        self.write(install=[{'os': 'any', 'run': [sys.executable, '-c', 'raise SystemExit(3)']},
                            {'os': 'any', 'run': [sys.executable, '-c', 'open(%r,"w")' % self.marker]}])
        done = self.go('install', '--yes')
        self.assertEqual(done.returncode, 1)
        self.assertIn('step failed (exit 3)', done.stdout)

    def test_an_alternative_is_used_when_the_first_tool_is_missing(self):
        self.write(install=[{'os': 'any', 'run': ['no-such-tool-xyz', 'x'], 'requires': 'no-such-tool-xyz'},
                            {'os': 'any', 'run': [sys.executable, '-c', 'open(%r,"w")' % self.marker], 'why': 'fallback'}])
        done = self.go('install', '--yes')
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(os.path.exists(self.marker))

    def test_a_downloaded_script_is_hashed_and_shown_before_it_runs(self):
        import shutil as _shutil, pathlib as _pathlib
        shell = 'sh' if _shutil.which('sh') else sys.executable
        ext = '.sh' if shell == 'sh' else '.py'
        script = os.path.join(self.tmp.name, 'inst' + ext)
        with open(script, 'w') as f:
            if shell == sys.executable:
                f.write('open(%r,"w").write("ran")\n' % self.marker)
            else:
                f.write('echo ran > "%s"\n' % self.marker)
        self.write(install=[{'os': 'any', 'script': _pathlib.Path(script).as_uri(), 'shell': shell}])
        done = self.go('install', '--yes')
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertRegex(done.stdout, r'sha256 [0-9a-f]{64}')
        self.assertTrue(os.path.exists(self.marker))

    def test_a_script_over_plain_http_is_refused(self):
        with self.assertRaises(SystemExit):
            sfp_app.fetch_script('http://example.com/x.sh')

    def test_status_sees_a_service_that_answers(self):
        srv = http.server.HTTPServer(('127.0.0.1', 0), Quiet)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            self.write(health='http://127.0.0.1:%d/' % srv.server_port)
            open(self.marker, 'w').close()
            done = self.go('status')
            self.assertIn('installed, running', done.stdout)
            self.assertEqual(self.go('start').returncode, 0)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_status_says_not_running_when_nothing_answers(self):
        self.write(health='http://127.0.0.1:9/')
        open(self.marker, 'w').close()
        self.assertIn('installed, not running', self.go('status').stdout)

    def test_version_ranges(self):
        r = [[22, 22, 2], [23, 0, 0], [24, 0, 0], [27, 0, 0]]
        for v, ok in (((22, 22, 2), True), ((22, 22, 0), False), ((22, 23, 0), True), ((23, 1, 0), False), ((24, 0, 0), True), ((26, 9, 9), True), ((27, 0, 0), False)):
            self.assertEqual(sfp_app.in_range(v, r), ok, v)

    def test_a_table_needs_an_id(self):
        with open(self.reg, 'w', encoding='utf-8') as f:
            json.dump({'a': dict(name='A', what='x', install=[]), 'b': dict(name='B', what='y', install=[{'os': 'any', 'run': ['x']}])}, f)
        self.assertNotEqual(self.go('status').returncode, 0)
        self.assertRegex(self.go('list').stdout, r'(?m)^a +x$')
        self.assertIn('Plan to install B', self.go('install', 'b').stdout)


class RegistryTest(unittest.TestCase):
    def test_every_entry_is_complete_and_installs_by_a_known_way(self):
        for key, app in APPS.items():
            for field in ('name', 'what', 'homepage', 'needs', 'install'):
                self.assertIn(field, app, key)
            for step in app['install'] + app.get('update', []):
                self.assertTrue(any(k in step for k in ('run', 'script', 'manual')), key)
                if 'script' in step:
                    self.assertTrue(step['script'].startswith('https://'), key)

    def test_every_source_named_is_a_real_source(self):
        with open(os.path.join(ROOT, 'sources.json'), encoding='utf-8') as f:
            repos = {s['repo'] for s in json.load(f)['sources']}
        for key, app in APPS.items():
            for repo in app.get('sources', []):
                self.assertIn(repo, repos, key)


class GeneratedSkillsTest(unittest.TestCase):
    def skills_of(self, key):
        return [s for s in SKILLS.values() if s.get('app') == key]

    def test_omniroute_skills_all_carry_the_setup(self):
        found = self.skills_of('omniroute')
        self.assertGreaterEqual(len(found), 40)
        for s in found:
            d = os.path.join(ROOT, s['path'])
            self.assertTrue(os.path.isfile(os.path.join(d, 'scripts', 'sfp_app.py')), s['name'])
            with open(os.path.join(d, 'scripts', 'app.json'), encoding='utf-8') as f:
                self.assertEqual(json.load(f)['id'], 'omniroute')
            with open(os.path.join(d, 'SKILL.md'), encoding='utf-8') as f:
                text = f.read()
            self.assertRegex(text, r'(?s)\A---\n.*?\n---\n\n> \*\*This skill needs OmniRoute', s['name'])

    def test_each_program_with_sources_has_skills(self):
        for key, app in APPS.items():
            if app.get('sources') or app.get('names'):
                self.assertTrue(self.skills_of(key), key)

    def test_the_engine_inside_a_skill_runs_on_its_own(self):
        d = os.path.join(ROOT, SKILLS['freellmapi']['path'], 'scripts')
        done = subprocess.run([sys.executable, '-I', os.path.join(d, 'sfp_app.py'), 'status'], capture_output=True, text=True, timeout=60,
                              env={k: v for k, v in os.environ.items() if k != 'SFP_APPS_FILE'})
        self.assertIn('FreeLLMAPI:', done.stdout)

    def test_the_router_lists_every_program(self):
        done = subprocess.run([sys.executable, '-I', os.path.join(ROOT, SKILLS['sfp']['path'], 'scripts', 'sfp_app.py'), 'list'],
                              capture_output=True, text=True, timeout=60)
        for key in APPS:
            self.assertRegex(done.stdout, r'(?m)^%s ' % re.escape(key))

    def test_the_frontmatter_is_still_first_so_the_skill_still_loads(self):
        for s in self.skills_of('strix'):
            with open(os.path.join(ROOT, s['path'], 'SKILL.md'), encoding='utf-8') as f:
                self.assertTrue(f.read().startswith('---\n'), s['name'])


if __name__ == '__main__':
    unittest.main()
