"""Drive the SFP MCP server over stdio with real JSON-RPC, the way a client does.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, 'mcp', 'sfp_mcp.py')


class Client:
    def __init__(self):
        env = dict(os.environ, SFP_ROOT=ROOT)
        self.p = subprocess.Popen([sys.executable, '-I', SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding='utf-8', env=env)
        self.n = 0

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj) + '\n')
        self.p.stdin.flush()

    def rpc(self, method, params=None):
        self.n += 1
        self.send({'jsonrpc': '2.0', 'id': self.n, 'method': method, 'params': params or {}})
        reply = json.loads(self.p.stdout.readline())
        assert reply['id'] == self.n, reply
        return reply

    def call(self, tool, **args):
        r = self.rpc('tools/call', {'name': tool, 'arguments': args})
        return r['result']['isError'], r['result']['content'][0]['text']

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)
        self.p.stdout.close()
        self.p.stderr.close()


class McpServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Client()
        init = cls.c.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                        'clientInfo': {'name': 'test', 'version': '0'}})
        cls.init = init['result']
        cls.c.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        with open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8') as f:
            cls.catalog = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def test_initialize_negotiates_and_advertises(self):
        self.assertEqual(self.init['protocolVersion'], '2025-06-18')
        self.assertEqual(self.init['serverInfo']['name'], 'sfp')
        for cap in ('tools', 'resources', 'prompts'):
            self.assertIn(cap, self.init['capabilities'])
        self.assertIn(str(len(self.catalog['skills'])), self.init['instructions'])

    def test_unknown_protocol_falls_back_to_a_supported_one(self):
        c = Client()
        try:
            r = c.rpc('initialize', {'protocolVersion': '1999-01-01'})
            self.assertEqual(r['result']['protocolVersion'], '2025-06-18')
        finally:
            c.close()

    def test_tools_list_is_complete_and_only_the_selector_writes(self):
        tools = {t['name']: t for t in self.c.rpc('tools/list')['result']['tools']}
        self.assertEqual(set(tools), {'search_skills', 'get_skill', 'read_skill_file', 'list_categories', 'find_api',
                                      'install_command', 'select_skills', 'give_feedback', 'learning_status', 'predict_next'})
        for name, t in tools.items():
            # select_skills and give_feedback write the selector's own logs in ~/.sfp, and nothing else does.
            self.assertEqual(t['annotations']['readOnlyHint'], name not in ('select_skills', 'give_feedback'))
            self.assertEqual(t['inputSchema']['type'], 'object')
            self.assertNotIn('fn', t)

    def test_search_finds_the_right_skill(self):
        err, text = self.c.call('search_skills', query='postgres schema migration', limit=5)
        self.assertFalse(err)
        names = [s['name'] for s in json.loads(text)['skills']]
        self.assertTrue({'postgres-patterns', 'database-migrations'} & set(names), names)
        err, text = self.c.call('search_skills', query='penetration testing', category='security')
        self.assertTrue(all(s['category'] == 'security' for s in json.loads(text)['skills']))

    def test_search_rejects_empty_and_bad_category(self):
        self.assertTrue(self.c.call('search_skills')[0])
        self.assertTrue(self.c.call('search_skills', query='x1', category='nope')[0])

    def test_get_skill_returns_instructions_and_files(self):
        err, text = self.c.call('get_skill', name='public-apis')
        self.assertFalse(err)
        self.assertIn('# Skill: public-apis', text)
        self.assertIn('scripts/find_api.py', text)
        self.assertIn('name: public-apis', text)

    def test_get_skill_unknown_suggests_close_matches(self):
        err, text = self.c.call('get_skill', name='postgres')
        self.assertTrue(err)
        self.assertIn('postgres-patterns', text)

    def test_read_skill_file_and_traversal_is_blocked(self):
        err, text = self.c.call('read_skill_file', name='public-apis', path='scripts/find_api.py')
        self.assertFalse(err)
        self.assertIn('def load', text)
        for bad in ('../../../../catalog.json', '/etc/passwd', '..\\..\\catalog.json', 'reference/../../../../catalog.json'):
            err, text = self.c.call('read_skill_file', name='public-apis', path=bad)
            self.assertTrue(err, bad)

    def test_find_api_bridges_to_the_bundled_search(self):
        err, text = self.c.call('find_api', query='cat facts', auth='none', cors='yes', limit=3)
        self.assertFalse(err)
        hits = json.loads(text)
        self.assertTrue(hits)
        self.assertTrue(all(h['auth'].lower() == 'no' and h['cors'].lower() == 'yes' for h in hits))

    def test_find_api_does_not_treat_input_as_flags_or_shell(self):
        err, text = self.c.call('find_api', query='--help; echo pwned $(id)')
        self.assertNotIn('uid=', text)

    def test_list_categories_and_install_command(self):
        err, text = self.c.call('list_categories')
        data = json.loads(text)
        self.assertEqual(data['total_skills'], len(self.catalog['skills']))
        self.assertIn('everything', data['presets'])
        err, text = self.c.call('install_command', categories='frontend,security', tools='cursor')
        self.assertFalse(err)
        self.assertIn('--categories frontend,security', text)
        self.assertTrue(self.c.call('install_command', categories='nope')[0])

    def test_unknown_tool_is_a_protocol_error(self):
        r = self.c.rpc('tools/call', {'name': 'nope', 'arguments': {}})
        self.assertEqual(r['error']['code'], -32602)

    def test_resources(self):
        listed = self.c.rpc('resources/list')['result']['resources']
        self.assertEqual(len(listed), len(self.catalog['skills']) + 1)
        r = self.c.rpc('resources/read', {'uri': 'sfp://skill/sfp'})['result']['contents'][0]
        self.assertIn('name: sfp', r['text'])
        cat = self.c.rpc('resources/read', {'uri': 'sfp://catalog'})['result']['contents'][0]
        self.assertIn('categories', json.loads(cat['text']))
        self.assertEqual(self.c.rpc('resources/read', {'uri': 'sfp://skill/nope'})['error']['code'], -32002)
        self.assertEqual(self.c.rpc('resources/read', {'uri': 'sfp://skill/../../etc/passwd'})['error']['code'], -32002)
        tpl = self.c.rpc('resources/templates/list')['result']['resourceTemplates']
        self.assertEqual(tpl[0]['uriTemplate'], 'sfp://skill/{name}')

    def test_prompts(self):
        names = {p['name'] for p in self.c.rpc('prompts/list')['result']['prompts']}
        self.assertEqual(names, {'use_skill', 'find_skill_for'})
        m = self.c.rpc('prompts/get', {'name': 'use_skill', 'arguments': {'name': 'sfp', 'task': 'build a form'}})['result']
        self.assertIn('build a form', m['messages'][0]['content']['text'])
        m = self.c.rpc('prompts/get', {'name': 'find_skill_for', 'arguments': {'task': 'animate a modal'}})['result']
        self.assertIn('animate', m['messages'][0]['content']['text'].lower())
        self.assertEqual(self.c.rpc('prompts/get', {'name': 'nope'})['error']['code'], -32602)
        self.assertEqual(self.c.rpc('prompts/get', {'name': 'use_skill', 'arguments': {'name': 'nope'}})['error']['code'], -32602)

    def test_ping_unknown_method_and_garbage(self):
        self.assertEqual(self.c.rpc('ping')['result'], {})
        self.assertEqual(self.c.rpc('does/not/exist')['error']['code'], -32601)
        self.c.p.stdin.write('this is not json\n')
        self.c.p.stdin.flush()
        self.assertEqual(json.loads(self.c.p.stdout.readline())['error']['code'], -32700)
        self.assertEqual(self.c.rpc('ping')['result'], {})  # still alive


if __name__ == '__main__':
    unittest.main()
