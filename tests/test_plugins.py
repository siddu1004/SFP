"""The plugin files for each IDE are generated from the same categories and agree with each other.

Shape only: these tests cannot run Codex, Cursor, Copilot or Gemini. Claude Code's own validator is run
separately (`claude plugin validate .`).

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as f:
        return json.load(f)


class PluginFilesTest(unittest.TestCase):
    def test_every_marketplace_lists_the_same_plugins_that_exist_on_disk(self):
        claude = [p['name'] for p in load('.claude-plugin', 'marketplace.json')['plugins'] if isinstance(p['source'], str)]
        cursor = [p['name'] for p in load('.cursor-plugin', 'marketplace.json')['plugins']]
        codex = [p['name'] for p in load('.agents', 'plugins', 'marketplace.json')['plugins']]
        self.assertEqual(claude, cursor)
        self.assertEqual(claude, codex)
        for name in claude:
            self.assertTrue(os.path.isdir(os.path.join(ROOT, 'plugins', name, 'skills')), name)

    def test_every_plugin_has_each_manifest_and_they_agree(self):
        for p in load('.agents', 'plugins', 'marketplace.json')['plugins']:
            d = os.path.join(ROOT, p['source']['path'])
            self.assertEqual(p['source']['source'], 'local')
            claude = load(d, '.claude-plugin', 'plugin.json')
            root = load(d, 'plugin.json')
            codex = load(d, '.codex-plugin', 'plugin.json')
            for m in (claude, root, codex):
                self.assertEqual(m['name'], p['name'])
                self.assertEqual(m['skills'], './skills/')
                self.assertRegex(m['name'], r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$')
            self.assertEqual(root, claude)
            self.assertIn('interface', codex)

    def test_the_gemini_extension_serves_the_mcp_server_that_exists(self):
        ext = load('gemini-extension.json')
        self.assertEqual(ext['name'], 'sfp')
        arg = ext['mcpServers']['sfp']['args'][0]
        self.assertTrue(arg.startswith('${extensionPath}/'))
        self.assertTrue(os.path.isfile(os.path.join(ROOT, arg.replace('${extensionPath}/', ''))))

    def test_the_gemini_server_starts_from_another_folder(self):
        req = '\n'.join(json.dumps(m) for m in (
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '1'}}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'list_categories', 'arguments': {}}})) + '\n'
        env = {k: v for k, v in os.environ.items() if k != 'SFP_ROOT'}
        import tempfile
        with tempfile.TemporaryDirectory() as elsewhere:
            done = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'mcp', 'sfp_mcp.py')], input=req, capture_output=True, text=True,
                                  cwd=elsewhere, env=env, timeout=60)
        self.assertIn('%d skills' % len(load('catalog.json')['skills']), done.stdout)


if __name__ == '__main__':
    unittest.main()
