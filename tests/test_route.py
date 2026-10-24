"""The model router (mcp/sfp_route.py), against fake model servers on localhost: ordering by size and policy, failover on
rate limits and dead servers, cooldowns, streaming, tools, local discovery, and that no key or text is stored.

Run:  python3 -m unittest discover -s tests -v
"""
import http.client
import http.server
import json
import os
import socketserver
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_route as rt  # noqa: E402


class Fake:
    """A model server: answers chat requests the way you tell it to, and remembers what it was asked."""

    def __init__(self, name, status=200, retry_after=None, stream=False):
        self.name, self.status, self.retry_after, self.stream = name, status, retry_after, stream
        self.calls, self.last_body, self.last_auth = 0, None, None
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *a):
                pass

            def do_GET(self):
                data = json.dumps({'data': [{'id': outer.name}]} if self.path.endswith('/models') else
                                  {'models': [{'name': outer.name}, {'name': 'nomic-embed-text'}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                outer.calls += 1
                outer.last_body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.last_auth = self.headers.get('Authorization')
                if outer.status != 200:
                    self.send_response(outer.status)
                    if outer.retry_after:
                        self.send_header('Retry-After', str(outer.retry_after))
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                if outer.stream:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    for part in ('hel', 'lo'):
                        self.wfile.write(('data: {"choices":[{"delta":{"content":"%s"}}]}\n\n' % part).encode())
                        self.wfile.flush()
                    self.wfile.write(b'data: [DONE]\n\n')
                    self.close_connection = True
                    return
                data = json.dumps({'model': outer.name, 'choices': [{'message': {'role': 'assistant', 'content': 'from ' + outer.name}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

        self.srv = S(('127.0.0.1', 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    @property
    def base(self):
        return 'http://127.0.0.1:%d/v1' % self.port

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()


def provider(pid, fake, kind='local', models=None, key=''):
    return {'id': pid, 'name': pid, 'kind': kind, 'base_url': fake.base, 'api_key_env': key,
            'models': models or [{'id': fake.name, 'strength': 2, 'ctx': 8192, 'tools': True}]}


class RouterCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get('SFP_DATA_DIR')
        os.environ['SFP_DATA_DIR'] = self.tmp.name
        self.fakes, self.servers = [], []

    def tearDown(self):
        for s in self.servers:
            s.shutdown()
            s.server_close()
        for f in self.fakes:
            if f.srv:
                f.stop()
        if self.old is None:
            os.environ.pop('SFP_DATA_DIR', None)
        else:
            os.environ['SFP_DATA_DIR'] = self.old
        self.tmp.cleanup()

    def fake(self, *a, **k):
        f = Fake(*a, **k)
        self.fakes.append(f)
        return f

    def router(self, providers, policy='local-first', token=None):
        srv, state = rt.make_server({'policy': policy, 'providers': providers}, 0, token)
        self.servers.append(srv)
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        self.port, self.state = srv.server_address[1], state
        return state

    def post(self, body, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        c.request('POST', '/v1/chat/completions', json.dumps(body), dict({'Content-Type': 'application/json'}, **(headers or {})))
        r = c.getresponse()
        data = r.read()
        c.close()
        return r, data

    def ask(self, text='hi', **extra):
        return self.post(dict({'model': 'auto', 'messages': [{'role': 'user', 'content': text}]}, **extra))


class OrderingTest(RouterCase):
    def test_a_light_request_uses_the_small_local_model_and_a_heavy_one_the_strong_cloud_model(self):
        small, big, cloud = self.fake('small-3b'), self.fake('big-70b'), self.fake('cloud-70b')
        self.router([provider('local', small, models=[{'id': 'small-3b', 'strength': 1, 'ctx': 8192}]),
                     provider('mid', big, models=[{'id': 'big-70b', 'strength': 3, 'ctx': 32768}]),
                     provider('cl', cloud, 'free', [{'id': 'cloud-70b', 'strength': 3, 'ctx': 32768}])])
        r, _ = self.ask('rename this variable')
        self.assertEqual((r.status, r.getheader('X-SFP-Model'), r.getheader('X-SFP-Tier')), (200, 'local/small-3b', 'light'))
        r, _ = self.ask('Refactor the architecture of the billing service to remove the circular dependencies')
        self.assertEqual((r.getheader('X-SFP-Model'), r.getheader('X-SFP-Tier')), ('mid/big-70b', 'heavy'))
        self.assertEqual(cloud.calls, 0)

    def test_policies_change_the_order(self):
        a, b = self.fake('local-7b'), self.fake('cloud-70b')
        provs = [provider('l', a, models=[{'id': 'local-7b', 'strength': 1, 'ctx': 8192}]),
                 provider('c', b, 'free', [{'id': 'cloud-70b', 'strength': 3, 'ctx': 32768}])]
        for policy, first in (('local-first', 'l'), ('cheap-first', 'l'), ('strong-first', 'c')):
            order, _ = rt.candidates({'policy': policy, 'providers': provs}, {'messages': [{'role': 'user', 'content': 'hi'}]}, rt.State())
            self.assertEqual(order[0][0]['id'], first, policy)

    def test_a_model_with_too_little_room_or_no_tools_is_skipped(self):
        a, b = self.fake('tiny'), self.fake('roomy')
        self.router([provider('a', a, models=[{'id': 'tiny', 'strength': 1, 'ctx': 2048, 'tools': False}]),
                     provider('b', b, models=[{'id': 'roomy', 'strength': 2, 'ctx': 32768}])])
        r, _ = self.ask('x' * 12000)
        self.assertEqual(r.getheader('X-SFP-Model'), 'b/roomy')
        r, _ = self.ask('hi', tools=[{'type': 'function', 'function': {'name': 'f'}}])
        self.assertEqual(r.getheader('X-SFP-Model'), 'b/roomy')

    def test_a_named_model_is_honoured(self):
        a, b = self.fake('one'), self.fake('two')
        self.router([provider('a', a), provider('b', b, models=[{'id': 'two', 'strength': 2, 'ctx': 8192}])])
        r, _ = self.post({'model': 'b/two', 'messages': [{'role': 'user', 'content': 'hi'}]})
        self.assertEqual(r.getheader('X-SFP-Model'), 'b/two')


class FailoverTest(RouterCase):
    def test_a_rate_limited_model_cools_down_and_the_next_one_answers(self):
        a, b = self.fake('limited', status=429, retry_after=7), self.fake('spare')
        state = self.router([provider('a', a), provider('b', b)])
        r, data = self.ask()
        self.assertEqual((r.status, r.getheader('X-SFP-Model')), (200, 'b/spare'))
        self.assertIn('from spare', data.decode())
        self.assertEqual(a.calls, 1)
        c = state.cooling('a/limited')
        self.assertTrue(c and 5 < c['until'] - time.time() <= 7.5)
        self.ask()
        self.assertEqual(a.calls, 1)                    # still cooling: not asked again

    def test_a_dead_server_and_a_key_error_are_skipped(self):
        dead, bad, ok = self.fake('dead'), self.fake('badkey', status=401), self.fake('fine')
        dead.stop()
        self.router([provider('d', dead), provider('k', bad), provider('f', ok)])
        r, _ = self.ask()
        self.assertEqual(r.getheader('X-SFP-Model'), 'f/fine')

    def test_when_every_model_fails_the_error_says_why(self):
        a, b = self.fake('a', status=500), self.fake('b', status=429)
        self.router([provider('a', a), provider('b', b)])
        r, data = self.ask()
        self.assertEqual(r.status, 503)
        msg = json.loads(data)['error']['message']
        self.assertIn('a/a (error 500)', msg)
        self.assertIn('b/b (rate limited)', msg)

    def test_a_cooling_model_is_the_last_resort_not_a_dead_end(self):
        a = self.fake('only')
        state = self.router([provider('a', a)])
        state.fail('a/only', 'rate limited', 60)
        r, _ = self.ask()
        self.assertEqual(r.status, 200)                 # the only model is tried anyway

    def test_a_weak_model_is_used_when_the_strong_ones_are_down(self):
        weak, strong = self.fake('weak'), self.fake('strong', status=429)
        self.router([provider('w', weak, models=[{'id': 'weak', 'strength': 1, 'ctx': 8192}]),
                     provider('s', strong, 'free', [{'id': 'strong', 'strength': 3, 'ctx': 8192}])])
        r, _ = self.ask('Refactor the architecture of the whole service')
        self.assertEqual(r.getheader('X-SFP-Model'), 'w/weak')

    def test_the_cooldown_doubles_and_is_capped(self):
        s = rt.State()
        for _ in range(8):
            s.fail('k', 'rate limited', now=1000)
        self.assertEqual(s.cool['k']['until'], 1000 + rt.COOL_MAX)
        s.ok('k')
        self.assertIsNone(s.cooling('k', now=1001))


class StreamingAndKeysTest(RouterCase):
    def test_a_stream_is_passed_through_chunk_by_chunk(self):
        a = self.fake('streamer', stream=True)
        self.router([provider('a', a)])
        r, data = self.ask(stream=True)
        self.assertEqual(r.getheader('Content-Type'), 'text/event-stream')
        self.assertIn('"hel"', data.decode())
        self.assertTrue(data.decode().rstrip().endswith('[DONE]'))

    def test_the_provider_key_is_sent_and_the_client_key_is_not(self):
        a = self.fake('keyed')
        os.environ['SFP_TEST_KEY'] = 'upstream-secret'
        try:
            self.router([provider('a', a, 'free', key='SFP_TEST_KEY')])
            self.post({'model': 'auto', 'messages': [{'role': 'user', 'content': 'hi'}]}, {'Authorization': 'Bearer client-key'})
            self.assertEqual(a.last_auth, 'Bearer upstream-secret')
            self.assertEqual(a.last_body['model'], 'keyed')
        finally:
            os.environ.pop('SFP_TEST_KEY')

    def test_a_provider_without_its_key_is_not_a_candidate(self):
        a, b = self.fake('nokey'), self.fake('open')
        os.environ.pop('SFP_MISSING_KEY', None)
        self.router([provider('a', a, 'free', key='SFP_MISSING_KEY'), provider('b', b)])
        r, _ = self.ask()
        self.assertEqual((r.getheader('X-SFP-Model'), a.calls), ('b/open', 0))

    def test_a_token_is_required_when_set(self):
        a = self.fake('guarded')
        self.router([provider('a', a)], token='sesame')
        self.assertEqual(self.ask()[0].status, 401)
        r, _ = self.post({'messages': [{'role': 'user', 'content': 'hi'}]}, {'Authorization': 'Bearer sesame'})
        self.assertEqual(r.status, 200)

    def test_nothing_secret_or_textual_is_written_to_disk(self):
        a = self.fake('quiet')
        os.environ['SFP_TEST_KEY'] = 'upstream-secret'
        try:
            self.router([provider('a', a, 'free', key='SFP_TEST_KEY')])
            self.ask('my private question about the merger')
            rt.save_config({'providers': [provider('a', a, 'free', key='SFP_TEST_KEY')]})
            blob = ''
            for name in os.listdir(self.tmp.name):
                with open(os.path.join(self.tmp.name, name), encoding='utf-8') as f:
                    blob += f.read()
            self.assertNotIn('upstream-secret', blob)
            self.assertNotIn('merger', blob)
            self.assertIn('SFP_TEST_KEY', blob)
        finally:
            os.environ.pop('SFP_TEST_KEY')

    def test_models_and_health_endpoints(self):
        a = self.fake('listed')
        self.router([provider('a', a)])
        for path, key in (('/v1/models', 'data'), ('/health', 'models')):
            c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
            c.request('GET', path)
            self.assertIn(key, json.loads(c.getresponse().read()))
            c.close()


class DiscoveryTest(RouterCase):
    def test_local_runtimes_are_found_and_embedding_models_left_out(self):
        ollama, studio = self.fake('qwen2.5-coder:7b'), self.fake('llama-3.1-70b-instruct')
        runtimes = [('ollama', 'Ollama', ollama.base, 'http://127.0.0.1:%d/api/tags' % ollama.port),
                    ('lmstudio', 'LM Studio', studio.base, studio.base + '/models'),
                    ('jan', 'Jan', 'http://127.0.0.1:1/v1', 'http://127.0.0.1:1/v1/models')]
        found = rt.discover(runtimes, timeout=2)
        self.assertEqual([f['runtime'] for f in found], ['ollama', 'lmstudio'])
        self.assertEqual(found[0]['models'], ['qwen2.5-coder:7b'])
        cfg = rt.build_config(found, env={})
        strengths = {m['id']: m['strength'] for p in cfg['providers'] for m in p['models']}
        self.assertEqual(strengths, {'qwen2.5-coder:7b': 1, 'llama-3.1-70b-instruct': 3})

    def test_keys_that_are_set_add_cloud_providers_by_name_only(self):
        cfg = rt.build_config([], env={'GROQ_API_KEY': 'x'})
        self.assertEqual([p['id'] for p in cfg['providers']], ['groq'])
        self.assertEqual(cfg['providers'][0]['api_key_env'], 'GROQ_API_KEY')
        self.assertNotIn('"x"', json.dumps(cfg))

    def test_strength_is_guessed_from_the_name(self):
        for name, want in (('llama3.2:3b', 1), ('qwen2.5-coder:14b', 2), ('llama-3.3-70b-versatile', 3), ('phi-mini', 1),
                           ('mystery-model', 2), ('gpt-4o-mini', 1)):
            self.assertEqual(rt.strength_of(name), want, name)

    def test_the_plan_lists_the_order(self):
        a, b = self.fake('a-7b'), self.fake('b-70b')
        cfg = {'providers': [provider('l', a, models=[{'id': 'a-7b', 'strength': 1, 'ctx': 8192}]),
                             provider('c', b, 'free', [{'id': 'b-70b', 'strength': 3, 'ctx': 32768}])]}
        text = rt.plan_text(cfg, 'rename this')
        self.assertIn('light', text)
        self.assertLess(text.index('l/a-7b'), text.index('c/b-70b'))


if __name__ == '__main__':
    unittest.main()
