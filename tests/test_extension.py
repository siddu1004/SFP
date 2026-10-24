"""The Antigravity / VS Code extension: its manifest agrees with its code. The extension's own tests run with
`npm test` in extensions/antigravity-hive; these checks need only Python.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, 'extensions', 'antigravity-hive')


def read(*parts):
    with open(os.path.join(EXT, *parts), encoding='utf-8') as f:
        return f.read()


class ExtensionManifestTest(unittest.TestCase):
    def setUp(self):
        self.pkg = json.loads(read('package.json'))
        self.code = read('src', 'extension.ts')

    def test_every_declared_command_is_registered_and_the_reverse(self):
        declared = {c['command'] for c in self.pkg['contributes']['commands']}
        registered = set(re.findall(r"reg\('(sfpHive\.\w+)'", self.code))
        registered |= {'sfpHive.' + v for v in ('helped', 'unhelpful', 'ignored')}   # registered in a loop
        self.assertEqual(declared, registered)

    def test_menus_only_name_declared_commands(self):
        declared = {c['command'] for c in self.pkg['contributes']['commands']}
        for items in self.pkg['contributes']['menus'].values():
            for item in items:
                self.assertIn(item['command'], declared)

    def test_the_view_the_code_registers_is_the_view_declared(self):
        views = [v['id'] for vs in self.pkg['contributes']['views'].values() for v in vs]
        self.assertIn('sfpHive.stack', views)
        self.assertIn("'sfpHive.stack'", self.code)

    def test_settings_the_code_reads_are_declared(self):
        declared = {k.split('.', 1)[1] for k in self.pkg['contributes']['configuration']['properties']}
        used = set(re.findall(r"c\.get(?:<\w+>)?\('(\w+)'", self.code))
        self.assertTrue(used)
        self.assertLessEqual(used, declared)

    def test_files_the_manifest_points_at_exist(self):
        for rel in (self.pkg['icon'], 'media/hive.svg', 'src/extension.ts', 'src/hive.ts', 'install.py', 'verify.py'):
            self.assertTrue(os.path.isfile(os.path.join(EXT, rel)), rel)
        self.assertEqual(self.pkg['main'], './out/extension.js')

    def test_no_secret_or_key_is_written_into_the_extension(self):
        for rel in ('package.json', 'src/extension.ts', 'src/hive.ts', 'install.py', 'test/hive.test.js', 'test/extension.test.js'):
            self.assertIsNone(re.search(r'sk-[0-9a-f]{8,}', read(*rel.split('/'))), rel)

    def test_the_licence_is_mit_like_the_rest_of_the_repo(self):
        self.assertEqual(self.pkg['license'], 'MIT')


class VerifyScriptTest(unittest.TestCase):
    """verify.py: the command-line check that the extension is installed in an editor and can work."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location('verify_ext', os.path.join(EXT, 'verify.py'))
        cls.v = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.v)

    def home(self):
        import tempfile
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return d.name

    def install(self, home, activation=True):
        import shutil
        folder = os.path.join(home, '.antigravity', 'extensions', 'siddu1004.sfp-hive-0.1.0')
        os.makedirs(os.path.join(folder, 'out'))
        pkg = json.loads(read('package.json'))
        if not activation:
            pkg.pop('activationEvents')
        with open(os.path.join(folder, 'package.json'), 'w') as f:
            json.dump(pkg, f)
        with open(os.path.join(folder, 'out', 'extension.js'), 'w') as f:
            f.write('')
        return folder

    def result(self, home, name):
        return next(r for r in self.v.run_checks(home=home) if r['check'] == name)

    def test_finds_the_extension_in_any_editors_folder(self):
        home = self.home()
        self.assertEqual(self.v.find_installed(home), [])
        folder = self.install(home)
        self.assertEqual(self.v.find_installed(home), [folder])
        self.assertEqual(self.result(home, 'extension folder on disk')['status'], 'PASS')

    def test_a_build_without_startup_activation_fails(self):
        home = self.home()
        self.install(home, activation=False)
        self.assertEqual(self.result(home, 'installed copy activates at startup and has its code')['status'], 'FAIL')
        home2 = self.home()
        self.install(home2)
        self.assertEqual(self.result(home2, 'installed copy activates at startup and has its code')['status'], 'PASS')

    def test_the_logs_are_read_for_errors_from_this_extension(self):
        home = self.home()
        logdir = os.path.join(home, '.config', 'Antigravity', 'logs', '20261024T010101', 'window1', 'exthost')
        os.makedirs(logdir)
        with open(os.path.join(logdir, 'exthost.log'), 'w') as f:
            f.write('info Extension siddu1004.sfp-hive activated\n')
        self.assertEqual(self.result(home, 'editor logs show the extension starting')['status'], 'PASS')
        with open(os.path.join(logdir, 'exthost.log'), 'a') as f:
            f.write('error Cannot find module for siddu1004.sfp-hive\n')
        self.assertEqual(self.result(home, 'editor logs show the extension starting')['status'], 'FAIL')

    def test_no_logs_is_a_skip_not_a_failure(self):
        self.assertEqual(self.result(self.home(), 'editor logs show the extension starting')['status'], 'SKIP')

    def test_the_real_hive_is_run(self):
        res = self.result(self.home(), 'the hive answers')
        self.assertEqual(res['status'], 'PASS', res['detail'])


if __name__ == '__main__':
    unittest.main()
