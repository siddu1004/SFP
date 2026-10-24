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
        for rel in (self.pkg['icon'], 'media/hive.svg', 'src/extension.ts', 'src/hive.ts', 'install.py'):
            self.assertTrue(os.path.isfile(os.path.join(EXT, rel)), rel)
        self.assertEqual(self.pkg['main'], './out/extension.js')

    def test_no_secret_or_key_is_written_into_the_extension(self):
        for rel in ('package.json', 'src/extension.ts', 'src/hive.ts', 'install.py', 'test/hive.test.js', 'test/extension.test.js'):
            self.assertIsNone(re.search(r'sk-[0-9a-f]{8,}', read(*rel.split('/'))), rel)

    def test_the_licence_is_mit_like_the_rest_of_the_repo(self):
        self.assertEqual(self.pkg['license'], 'MIT')


if __name__ == '__main__':
    unittest.main()
