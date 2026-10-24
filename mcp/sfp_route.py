#!/usr/bin/env python3
"""A small local router for language models: your local models first, then free tiers, then paid, and the next one
takes over when a model is rate limited, out of quota, down, or too small for the job. Standard library only.

It speaks the OpenAI chat API (`/v1/chat/completions`, `/v1/models`), so any tool that lets you set a base URL can use it:
point the tool at `http://127.0.0.1:8787/v1`, any key, and the model `auto`.

  sfp_route.py discover            find the models running on this machine (Ollama, LM Studio, llama.cpp, Jan, vLLM)
  sfp_route.py setup [--yes]       write routes.json from what was found and from the keys that are set
  sfp_route.py status              what each model is doing: ready, cooling down and why, requests served
  sfp_route.py serve [--port N]    run the router (127.0.0.1 only)
  sfp_route.py plan "<task>"       which model would be tried first, and in what order the others follow

How it chooses. Every request is sized: `light` (a short question, a rename), `normal`, or `heavy` (tools with a long
context, or words like architecture, refactor, security audit). Every model has a `strength` 1 to 3 (from its name if you
do not say) and a `ctx`. A model is a candidate when it has the room, takes tools if the request uses them, and its key
is set. Strong enough models come first, ordered by your `policy`: `local-first` (default: the weakest model that is
strong enough, local before cloud, so free and private is used whenever it can do the job), `cheap-first`, or
`strong-first`. Models that are too weak come last, as a final resort. When a model answers 429, 5xx, 401/402/403,
times out or is unreachable, it cools down (Retry-After honoured, else 30 s doubling to 10 min) and the next one is
tried, before any byte has been sent to the client. A stream that has started cannot be moved.

Keys are never stored: `routes.json` holds the *name* of the environment variable, read when a request is sent, and the
router never logs request text. It listens on 127.0.0.1 only. The client's own Authorization header is not forwarded.
"""
import argparse
import http.client
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

COOL_MIN, COOL_MAX = 30, 600
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 180

# What a local runtime looks like when it is running: (id, name, base url, how to list its models).
LOCAL_RUNTIMES = [
    ('ollama', 'Ollama', 'http://127.0.0.1:11434/v1', 'http://127.0.0.1:11434/api/tags'),
    ('lmstudio', 'LM Studio', 'http://127.0.0.1:1234/v1', 'http://127.0.0.1:1234/v1/models'),
    ('llamacpp', 'llama.cpp server', 'http://127.0.0.1:8080/v1', 'http://127.0.0.1:8080/v1/models'),
    ('jan', 'Jan', 'http://127.0.0.1:1337/v1', 'http://127.0.0.1:1337/v1/models'),
    ('vllm', 'vLLM', 'http://127.0.0.1:8000/v1', 'http://127.0.0.1:8000/v1/models'),
]

# Cloud providers added when their key is set: (id, name, base url, env var, kind, [(model, strength)]).
CLOUD = [
    ('groq', 'Groq', 'https://api.groq.com/openai/v1', 'GROQ_API_KEY', 'free', [('llama-3.3-70b-versatile', 3)]),
    ('openrouter', 'OpenRouter', 'https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY', 'free',
     [('deepseek/deepseek-chat-v3-0324:free', 3), ('meta-llama/llama-3.3-70b-instruct:free', 3)]),
    ('cerebras', 'Cerebras', 'https://api.cerebras.ai/v1', 'CEREBRAS_API_KEY', 'free', [('llama-3.3-70b', 3)]),
    ('gemini', 'Google AI Studio', 'https://generativelanguage.googleapis.com/v1beta/openai', 'GEMINI_API_KEY', 'free',
     [('gemini-2.0-flash', 3)]),
    ('mistral', 'Mistral', 'https://api.mistral.ai/v1', 'MISTRAL_API_KEY', 'free', [('mistral-small-latest', 2)]),
    ('openai', 'OpenAI', 'https://api.openai.com/v1', 'OPENAI_API_KEY', 'paid', [('gpt-4o-mini', 2), ('gpt-4o', 3)]),
]

HEAVY_WORDS = re.compile(r'\b(architect\w*|refactor\w*|migrat\w+|security (audit|review)|root cause|design (a|the) system|'
                         r'distributed|concurren\w+|race condition|prove|optimi[sz]e the (algorithm|query plan))\b', re.I)
LIGHT_WORDS = re.compile(r'\b(rename|typo|format|fix (the )?(indent|spacing)|what does|explain this line|summari[sz]e)\b', re.I)


def data_dir():
    return os.environ.get('SFP_DATA_DIR') or os.path.join(os.path.expanduser('~'), '.sfp')


def routes_path():
    return os.path.join(data_dir(), 'routes.json')


def strength_of(model_id):
    """1 small, 2 medium, 3 large, guessed from the parameter count in the name; unknown names are 2."""
    name = re.sub(r'[-:_/]', ' ', model_id.lower())
    m = re.search(r'(\d+(?:\.\d+)?)\s*b\b', name)
    if m:
        b = float(m.group(1))
        return 1 if b < 10 else 2 if b < 40 else 3
    if re.search(r'\b(mini|small|tiny|nano|lite)\b', name):
        return 1
    if re.search(r'\b(large|opus|pro|405|gpt 4o|sonnet|deepseek)\b', name):
        return 3
    return 2


# ---- finding what is there -------------------------------------------------------------------------------------

def _get_json(url, timeout):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def discover(runtimes=None, timeout=1.5):
    """[{runtime, name, base_url, models:[ids]}] for each local runtime that answers."""
    found = []
    for rid, name, base, listing in (runtimes or LOCAL_RUNTIMES):
        try:
            data = _get_json(listing, timeout)
        except (OSError, ValueError, urllib.error.URLError):
            continue
        if 'models' in data:                       # Ollama's own listing
            ids = [m.get('name') or m.get('model') for m in data['models']]
        else:
            ids = [m.get('id') for m in data.get('data', [])]
        ids = [i for i in ids if i and 'embed' not in i.lower()]
        if ids:
            found.append({'runtime': rid, 'name': name, 'base_url': base, 'models': ids})
    return found


def build_config(found, env=None, policy='local-first'):
    env = os.environ if env is None else env
    providers = []
    for f in found:
        providers.append({'id': f['runtime'], 'name': f['name'], 'kind': 'local', 'base_url': f['base_url'], 'api_key_env': '',
                          'models': [{'id': m, 'strength': strength_of(m), 'ctx': 8192, 'tools': True} for m in f['models']]})
    for cid, name, base, var, kind, models in CLOUD:
        if env.get(var):
            providers.append({'id': cid, 'name': name, 'kind': kind, 'base_url': base, 'api_key_env': var,
                              'models': [{'id': m, 'strength': s, 'ctx': 32768, 'tools': True} for m, s in models]})
    return {'policy': policy, 'providers': providers}


def load_config(path=None):
    try:
        with open(path or routes_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'policy': 'local-first', 'providers': []}


def save_config(cfg, path=None):
    path = path or routes_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=1)
    return path


# ---- sizing a request and ordering the models ------------------------------------------------------------------

def _text(content):
    return content if isinstance(content, str) else json.dumps(content or '')


def size_request(body):
    """-> {tier: light|normal|heavy, tokens, tools}. Counts characters / 4; never stores the text."""
    msgs = body.get('messages') or []
    tokens = sum(len(_text(m.get('content'))) for m in msgs) // 4
    last = next((_text(m.get('content')) for m in reversed(msgs) if m.get('role') == 'user'), '')
    tools = bool(body.get('tools') or body.get('functions'))
    if HEAVY_WORDS.search(last) or (tools and tokens > 6000) or tokens > 20000:
        tier = 'heavy'
    elif (LIGHT_WORDS.search(last) and tokens < 2000 and not tools) or (tokens < 600 and not tools):
        tier = 'light'
    else:
        tier = 'normal'
    return {'tier': tier, 'tokens': tokens, 'tools': tools}


NEED_STRENGTH = {'light': 1, 'normal': 2, 'heavy': 3}
KIND_RANK = {'local': 0, 'free': 1, 'paid': 2}
ALIAS_STRENGTH = {'light': 1, 'small': 1, 'normal': 2, 'medium': 2, 'heavy': 3, 'large': 3, 'strong': 3}


class State:
    """Cooldowns and counters, in memory; one per router."""

    def __init__(self):
        self.lock = threading.Lock()
        self.cool = {}          # key -> {until, why, strikes}
        self.stats = {}         # key -> {ok, fail, last}

    @staticmethod
    def key(provider, model):
        return '%s/%s' % (provider['id'], model['id'])

    def cooling(self, key, now=None):
        with self.lock:
            c = self.cool.get(key)
        return c if c and c['until'] > (now or time.time()) else None

    def fail(self, key, why, retry_after=None, now=None):
        now = now or time.time()
        with self.lock:
            strikes = self.cool.get(key, {'strikes': 0})['strikes'] + 1
            wait = retry_after if retry_after else min(COOL_MIN * 2 ** (strikes - 1), COOL_MAX)
            self.cool[key] = {'until': now + wait, 'why': why, 'strikes': strikes}
            s = self.stats.setdefault(key, {'ok': 0, 'fail': 0, 'last': ''})
            s['fail'] += 1
            s['last'] = why

    def ok(self, key):
        with self.lock:
            self.cool.pop(key, None)
            s = self.stats.setdefault(key, {'ok': 0, 'fail': 0, 'last': ''})
            s['ok'] += 1


def candidates(cfg, body, state, now=None):
    """The models to try, in order, each as (provider, model), and the request's size."""
    size = size_request(body)
    want = body.get('model') or 'auto'
    policy = cfg.get('policy', 'local-first')
    floor = NEED_STRENGTH[size['tier']]
    if want.startswith('sfp/'):
        floor = ALIAS_STRENGTH.get(want[4:], floor)
    named = want not in ('auto', '') and not want.startswith('sfp/')
    pool = []
    for p in cfg.get('providers', []):
        if p.get('disabled'):
            continue
        for m in p.get('models', []):
            if named and want not in (m['id'], '%s/%s' % (p['id'], m['id'])):
                continue
            if size['tools'] and m.get('tools') is False:
                continue
            if size['tokens'] + 1024 > m.get('ctx', 8192):
                continue
            if p.get('api_key_env') and not os.environ.get(p['api_key_env']):
                continue
            pool.append((p, m))

    def rank(pm):
        p, m = pm
        s = m.get('strength', 2)
        enough = s >= floor
        cool = state.cooling(state.key(p, m), now) is not None
        k = KIND_RANK.get(p.get('kind', 'free'), 1)
        if policy == 'strong-first':
            order = (-s, k)
        elif policy == 'cheap-first':
            order = (k, s)
        else:   # local-first: local before cloud, the weakest model that is strong enough; too-weak ones last, strongest first
            order = (k, s) if enough else (-s, k)
        return (not enough, cool, order)
    return sorted(pool, key=rank), size


# ---- talking to a model ----------------------------------------------------------------------------------------

class Upstream(Exception):
    def __init__(self, why, retry_after=None):
        super().__init__(why)
        self.why, self.retry_after = why, retry_after


def _open(provider, model, body, timeout=READ_TIMEOUT):
    """Start the request; returns (HTTPResponse, connection). Raises Upstream for anything that should move on."""
    url = urllib.parse.urlparse(provider['base_url'].rstrip('/') + '/chat/completions')
    conn_cls = http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection
    conn = conn_cls(url.hostname, url.port, timeout=CONNECT_TIMEOUT)
    headers = {'Content-Type': 'application/json'}
    if provider.get('api_key_env'):
        headers['Authorization'] = 'Bearer ' + os.environ.get(provider['api_key_env'], '')
    try:
        conn.request('POST', url.path, json.dumps(dict(body, model=model['id'])).encode(), headers)
        conn.sock.settimeout(timeout)
        resp = conn.getresponse()
    except (OSError, http.client.HTTPException) as e:
        conn.close()
        raise Upstream('unreachable (%s)' % type(e).__name__)
    if resp.status in (401, 402, 403, 429) or resp.status >= 500:
        ra = resp.getheader('Retry-After')
        resp.read(2000)
        conn.close()
        try:
            ra = float(ra) if ra else None
        except ValueError:
            ra = None
        why = {429: 'rate limited', 402: 'out of credit', 401: 'key refused', 403: 'key refused'}.get(resp.status, 'error %d' % resp.status)
        raise Upstream(why, ra)
    return resp, conn


def log_usage(provider, model, size, ok, ms):
    try:
        os.makedirs(data_dir(), exist_ok=True)
        with open(os.path.join(data_dir(), 'route_usage.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': int(time.time()), 'provider': provider['id'], 'model': model['id'], 'tier': size['tier'],
                                'tokens_in': size['tokens'], 'ok': ok, 'ms': int(ms)}) + '\n')
    except OSError:
        pass


def plan_text(cfg, task, state=None):
    order, size = candidates(cfg, {'messages': [{'role': 'user', 'content': task}]}, state or State())
    lines = ['request: %s (about %d tokens)' % (size['tier'], size['tokens'])]
    for i, (p, m) in enumerate(order):
        lines.append('%d. %s/%s  strength %d  %s' % (i + 1, p['id'], m['id'], m.get('strength', 2), p.get('kind', '')))
    return '\n'.join(lines) if order else 'no models configured: run `sfp_route.py setup`'


def status(cfg, state):
    out, now = [], time.time()
    for p in cfg.get('providers', []):
        for m in p.get('models', []):
            key = state.key(p, m)
            c = state.cooling(key, now)
            s = state.stats.get(key, {'ok': 0, 'fail': 0, 'last': ''})
            out.append({'model': key, 'kind': p.get('kind'), 'strength': m.get('strength', 2),
                        'state': ('cooling down %ds: %s' % (c['until'] - now, c['why'])) if c else
                                 ('no key' if p.get('api_key_env') and not os.environ.get(p['api_key_env']) else 'ready'),
                        'ok': s['ok'], 'failed': s['fail'], 'last_error': s['last']})
    return {'policy': cfg.get('policy', 'local-first'), 'models': out}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    cfg = {}
    state = None
    token = None

    def log_message(self, *a):
        pass

    def _send(self, code, obj, extra=None):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _authorised(self):
        return not self.token or self.headers.get('Authorization', '') == 'Bearer ' + self.token

    def do_GET(self):
        if not self._authorised():
            return self._send(401, {'error': {'message': 'bad token'}})
        path = self.path.split('?')[0].rstrip('/')
        if path in ('/health', '/status'):
            return self._send(200, status(self.cfg, self.state))
        if path in ('/v1/models', '/models'):
            ids = ['auto', 'sfp/light', 'sfp/normal', 'sfp/heavy']
            for p in self.cfg.get('providers', []):
                ids += ['%s/%s' % (p['id'], m['id']) for m in p.get('models', [])]
            return self._send(200, {'object': 'list', 'data': [{'id': i, 'object': 'model', 'owned_by': 'sfp'} for i in ids]})
        self._send(404, {'error': {'message': 'not found'}})

    def do_POST(self):
        try:
            raw = self.rfile.read(int(self.headers.get('Content-Length') or 0))   # always drain, so the connection stays in step
        except (ValueError, OSError):
            raw = b''
        if not self._authorised():
            return self._send(401, {'error': {'message': 'bad token'}})
        if not self.path.split('?')[0].rstrip('/').endswith('/chat/completions'):
            return self._send(404, {'error': {'message': 'only /v1/chat/completions is routed'}})
        try:
            body = json.loads(raw or b'{}')
        except ValueError:
            return self._send(400, {'error': {'message': 'the body is not JSON'}})
        order, size = candidates(self.cfg, body, self.state)
        if not order:
            return self._send(503, {'error': {'message': 'no model can take this request (none configured, too small, or keys missing)'}})
        tried = []
        for i, (p, m) in enumerate(order):
            key = self.state.key(p, m)
            if self.state.cooling(key) and i < len(order) - 1:
                tried.append('%s (cooling down)' % key)
                continue
            t0 = time.time()
            try:
                resp, conn = _open(p, m, body)
            except Upstream as e:
                self.state.fail(key, e.why, e.retry_after)
                log_usage(p, m, size, False, (time.time() - t0) * 1000)
                tried.append('%s (%s)' % (key, e.why))
                continue
            try:
                self._relay(resp, p, m, size)
            finally:
                conn.close()
            self.state.ok(key)
            log_usage(p, m, size, True, (time.time() - t0) * 1000)
            return
        self._send(503, {'error': {'message': 'every model failed: ' + '; '.join(tried)}}, {'Retry-After': str(COOL_MIN)})

    def _relay(self, resp, p, m, size):
        self.send_response(resp.status)
        ctype = resp.getheader('Content-Type', 'application/json')
        self.send_header('Content-Type', ctype)
        self.send_header('X-SFP-Model', '%s/%s' % (p['id'], m['id']))
        self.send_header('X-SFP-Tier', size['tier'])
        if 'text/event-stream' in ctype:
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            while True:
                chunk = resp.read1(8192) if hasattr(resp, 'read1') else resp.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
            self.close_connection = True
        else:
            data = resp.read()
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(cfg, port=8787, token=None, state=None):
    h = type('H', (Handler,), {'cfg': cfg, 'state': state or State(), 'token': token})
    return Server(('127.0.0.1', port), h), h.state


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('discover')
    s = sub.add_parser('setup')
    s.add_argument('--policy', choices=['local-first', 'cheap-first', 'strong-first'], default='local-first')
    s.add_argument('--yes', action='store_true', help='write routes.json (otherwise only show it)')
    sub.add_parser('status')
    sv = sub.add_parser('serve')
    sv.add_argument('--port', type=int, default=8787)
    sv.add_argument('--token', default=os.environ.get('SFP_ROUTE_TOKEN'), help='require this bearer token (or set SFP_ROUTE_TOKEN)')
    pl = sub.add_parser('plan')
    pl.add_argument('task')
    a = ap.parse_args(argv)
    if a.cmd == 'discover':
        found = discover()
        if not found:
            print('No local model server answered on the usual ports (Ollama 11434, LM Studio 1234, llama.cpp 8080, Jan 1337, vLLM 8000).')
        for f in found:
            print('%s at %s: %s' % (f['name'], f['base_url'], ', '.join(f['models'])))
    elif a.cmd == 'setup':
        cfg = build_config(discover(), policy=a.policy)
        print(json.dumps(cfg, indent=1))
        if not cfg['providers']:
            print('\nNothing found. Start a local model server, or set a key (e.g. GROQ_API_KEY) and run this again.', file=sys.stderr)
        elif a.yes:
            print('\nwrote ' + save_config(cfg), file=sys.stderr)
        else:
            print('\nThis is what would be written to %s. Run again with --yes to write it.' % routes_path(), file=sys.stderr)
    elif a.cmd == 'status':
        print(json.dumps(status(load_config(), State()), indent=1))
    elif a.cmd == 'plan':
        print(plan_text(load_config(), a.task))
    elif a.cmd == 'serve':
        cfg = load_config()
        if not cfg['providers']:
            sys.exit('no models configured: run `sfp_route.py setup --yes` first')
        srv, _ = make_server(cfg, a.port, a.token)
        print('SFP router on http://127.0.0.1:%d/v1  (model: auto)' % a.port, flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
