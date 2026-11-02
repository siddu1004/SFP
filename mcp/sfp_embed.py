#!/usr/bin/env python3
"""Meaning search for the hive: skills and tasks as vectors from a local embedding model.

Keyword search misses a task that says the same thing in other words: "make the login safer" shares no word with
"authentication hardening". An embedding model maps both close together. This module asks a local runtime (LM Studio,
Ollama, llama.cpp, Jan or vLLM) for vectors, keeps the skills' vectors in a cache, and answers
"which skills mean what this task means" in a few milliseconds.

Nothing leaves the machine: only the local runtimes themselves are asked, never a router (port 8787), because a router
may fail over to a cloud model without saying so. SFP_EMBED_URL can still point anywhere you choose. With no embedding model running, or SFP_SEMANTIC=0, every
function here returns nothing and the hive works on words alone, as before.

CLI
  sfp_embed.py status                 the runtime and model found, and how much of the catalog is embedded
  sfp_embed.py build                  embed every skill (once; later runs only embed what changed)
  sfp_embed.py query "make login safer"
Env
  SFP_SEMANTIC=0                      turn meaning search off
  SFP_EMBED_URL, SFP_EMBED_MODEL      use this OpenAI-compatible endpoint and model instead of looking for one
"""
import array
import base64
import functools
import hashlib
import json
import math
import operator
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sfp_mcp as core  # noqa: E402  (the catalog)

# Where a model may be running: (name, OpenAI-compatible base url, how to list its models). Routers are left out on
# purpose: the SFP router, and others like it, fall back to cloud providers when a local model fails.
RUNTIMES = [
    ('LM Studio', 'http://127.0.0.1:1234/v1', 'http://127.0.0.1:1234/v1/models'),
    ('Ollama', 'http://127.0.0.1:11434/v1', 'http://127.0.0.1:11434/api/tags'),
    ('llama.cpp server', 'http://127.0.0.1:8080/v1', 'http://127.0.0.1:8080/v1/models'),
    ('Jan', 'http://127.0.0.1:1337/v1', 'http://127.0.0.1:1337/v1/models'),
    ('vLLM', 'http://127.0.0.1:8000/v1', 'http://127.0.0.1:8000/v1/models'),
]
EMBED_HINTS = ('embed', 'bge', 'e5-', 'gte', 'minilm', 'nomic')
EMBED_PREFERENCE = ('bge-m3', 'mxbai-embed', 'nomic-embed', 'bge', 'gte', 'e5-', 'minilm', 'embed')
EXAMPLES_FILE = os.path.join(core.ROOT, 'skill_examples.json')   # requests a developer might type, per skill
EXAMPLE_WEIGHT = 0.5     # a skill's closeness: half its description, half its closest example request
BATCH = 32
QUERY_TIMEOUT = 4.0     # a task waits at most this long for its vector, then the hive goes on with words alone
BUILD_TIMEOUT = 300.0


def enabled():
    return os.environ.get('SFP_SEMANTIC', '1').lower() not in ('0', 'false', 'no', 'off')


def data_dir():
    return os.environ.get('SFP_DATA_DIR') or os.path.join(os.path.expanduser('~'), '.sfp')


def _get_json(url, timeout):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def _ids(listing):
    if 'models' in listing:                                 # Ollama's own listing
        return [m.get('name') or m.get('model') for m in listing['models']]
    return [m.get('id') for m in listing.get('data', [])]


def find_endpoint(timeout=1.0, skip=()):
    """{'runtime', 'base_url', 'model'} of the first local embedding model that answers, or None. `skip` names runtimes
    not to ask (the SFP router skips itself)."""
    if os.environ.get('SFP_EMBED_URL') and os.environ.get('SFP_EMBED_MODEL'):
        return {'runtime': 'configured', 'base_url': os.environ['SFP_EMBED_URL'].rstrip('/'),
                'model': os.environ['SFP_EMBED_MODEL']}
    found = []
    for name, base, listing in RUNTIMES:
        if name in skip:
            continue
        try:
            ids = [i for i in _ids(_get_json(listing, timeout)) if i]
        except (OSError, ValueError, urllib.error.URLError):
            continue
        for i in ids:
            if any(h in i.lower() for h in EMBED_HINTS):
                found.append({'runtime': name, 'base_url': base, 'model': i})
    if not found:
        return None
    # The strongest model that is there: bge-m3 found the right skill in its top ten for 80% of reworded tasks.
    rank = lambda ep: next((k for k, h in enumerate(EMBED_PREFERENCE) if h in ep['model'].lower()), len(EMBED_PREFERENCE))
    return min(found, key=rank)


def _prefix(model, kind):
    """Some models are trained with a marker that says whether a text is a question or a document."""
    m = model.lower()
    if 'nomic' in m:
        return 'search_query: ' if kind == 'query' else 'search_document: '
    if 'e5' in m:
        return 'query: ' if kind == 'query' else 'passage: '
    return ''


def embed(endpoint, texts, kind='document', timeout=QUERY_TIMEOUT):
    """Unit vectors for the texts, in order. Raises OSError (or ValueError) when the runtime does not answer."""
    pre = _prefix(endpoint['model'], kind)
    body = json.dumps({'model': endpoint['model'], 'input': [pre + t for t in texts]}).encode()
    req = urllib.request.Request(endpoint['base_url'] + '/embeddings', body,
                                 {'Content-Type': 'application/json', 'Authorization': 'Bearer local'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode('utf-8'))
    rows = sorted(data['data'], key=lambda d: d.get('index', 0))
    if len(rows) != len(texts):
        raise ValueError('the runtime returned %d vectors for %d texts' % (len(rows), len(texts)))
    return [_unit(row['embedding']) for row in rows]


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


BODY_CHARS = 900


@functools.lru_cache(maxsize=None)
def _body_excerpt(path):
    """The opening prose of a SKILL.md: no frontmatter, code, tables, quoted notes or links, cut to BODY_CHARS."""
    try:
        with open(os.path.join(core.ROOT, path, 'SKILL.md'), encoding='utf-8', errors='replace') as f:
            text = f.read(20000)
    except OSError:
        return ''
    text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, count=1, flags=re.S)
    text = re.sub(r'```.*?(```|$)', ' ', text, flags=re.S)
    keep = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(('>', '|', '<', '!')):
            continue
        keep.append(re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s.lstrip('#*- ').replace('`', '')))
    return ' '.join(keep)[:BODY_CHARS]


def skill_text(s):
    """What a skill is about, as the model reads it: its name, category, description and how its SKILL.md opens."""
    return '%s (%s): %s %s' % (s['name'].replace('-', ' '), s['category'].replace('-', ' '), s['description'],
                               _body_excerpt(s['path']))


def _digest(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]


# ---- the cache: ~/.sfp/embeddings/<model>.json, one vector per skill, kept while the skill's text is unchanged ------

def cache_path(model, kind='skills'):
    safe = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in model)
    return os.path.join(data_dir(), 'embeddings', safe + ('' if kind == 'skills' else '.' + kind) + '.json')


def _pack(v):
    return base64.b64encode(array.array('f', v).tobytes()).decode('ascii')


def _unpack(s):
    a = array.array('f')
    a.frombytes(base64.b64decode(s))
    return a.tolist()


def load_cache(model, kind='skills'):
    """{skill: (digest, vector)}; for kind='examples', {skill: (digest, [vectors])}."""
    try:
        with open(cache_path(model, kind), encoding='utf-8') as f:
            data = json.load(f)
        if kind == 'examples':
            return {name: (d, [_unpack(x) for x in v]) for name, (d, v) in data.get('items', {}).items()}
        return {name: (d, _unpack(v)) for name, (d, v) in data.get('items', {}).items()}
    except (OSError, ValueError, TypeError):
        return {}


def save_cache(model, items, kind='skills'):
    path = cache_path(model, kind)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    pack = (lambda v: [_pack(x) for x in v]) if kind == 'examples' else _pack
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'model': model, 'items': {n: [d, pack(v)] for n, (d, v) in items.items()}}, f, separators=(',', ':'))
    os.replace(tmp, path)


def build(endpoint=None, progress=None, timeout=BUILD_TIMEOUT):
    """Embed every skill whose text is new or changed. Returns (embedded now, total)."""
    endpoint = endpoint or find_endpoint()
    if not endpoint:
        raise RuntimeError('no local embedding model found: load one in LM Studio or Ollama '
                           '(for example nomic-embed-text), or set SFP_EMBED_URL and SFP_EMBED_MODEL')
    items = load_cache(endpoint['model'])
    todo = []
    for s in core.CATALOG['skills']:
        text = skill_text(s)
        d = _digest(text)
        if items.get(s['name'], (None,))[0] != d:
            todo.append((s['name'], d, text))
    live = {s['name'] for s in core.CATALOG['skills']}
    items = {n: v for n, v in items.items() if n in live}
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        vecs = embed(endpoint, [t for _, _, t in chunk], 'document', timeout)
        for (name, d, _), v in zip(chunk, vecs):
            items[name] = (d, v)
        save_cache(endpoint['model'], items)
        if progress:
            progress(min(i + BATCH, len(todo)), len(todo))
    if not todo:
        save_cache(endpoint['model'], items)
    # The example requests are questions, so they are embedded as queries: a task is then matched question to question.
    examples = load_examples()
    ex_items = load_cache(endpoint['model'], kind='examples')
    ex_todo = [(n, _digest('\n'.join(qs)), qs) for n, qs in examples.items()
               if n in live and qs and ex_items.get(n, (None,))[0] != _digest('\n'.join(qs))]
    ex_items = {n: v for n, v in ex_items.items() if n in live and n in examples}
    flat = [(n, d, q) for n, d, qs in ex_todo for q in qs]
    vecs_of = {}
    for i in range(0, len(flat), BATCH):
        chunk = flat[i:i + BATCH]
        for (n, d, _), v in zip(chunk, embed(endpoint, [q for _, _, q in chunk], 'query', timeout)):
            vecs_of.setdefault((n, d), []).append(v)
        if progress:
            progress(min(i + BATCH, len(flat)), len(flat))
    for (n, d), vs in vecs_of.items():
        ex_items[n] = (d, vs)
    save_cache(endpoint['model'], ex_items, kind='examples')
    _index.cache_clear()
    return len(todo) + len(ex_todo), len(items)


def load_examples():
    try:
        with open(EXAMPLES_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ---- answering ---------------------------------------------------------------------------------------------------

_ENDPOINT = {'checked': 0.0, 'value': None}


def endpoint_cached(ttl=60.0):
    """The endpoint, looked up at most once a minute: a server process must not probe ports on every task."""
    if time.time() - _ENDPOINT['checked'] > ttl:
        _ENDPOINT['value'] = find_endpoint(timeout=0.5)
        _ENDPOINT['checked'] = time.time()
    return _ENDPOINT['value']


@functools.lru_cache(maxsize=4)
def _index(model):
    """(names, vectors, example vectors) for the skills whose cached vector matches their current text; a skill without
    current example vectors has []."""
    items = load_cache(model)
    ex_items = load_cache(model, kind='examples')
    examples = load_examples()
    names, vecs, exvecs = [], [], []
    for s in core.CATALOG['skills']:
        hit = items.get(s['name'])
        if hit and hit[0] == _digest(skill_text(s)):
            names.append(s['name'])
            vecs.append(hit[1])
            ex = ex_items.get(s['name'])
            qs = examples.get(s['name'])
            exvecs.append(ex[1] if ex and qs and ex[0] == _digest('\n'.join(qs)) else [])
    return names, vecs, exvecs


@functools.lru_cache(maxsize=256)
def _query_vector(base_url, model, text):
    return tuple(embed({'base_url': base_url, 'model': model}, [text], 'query')[0])


def similar(text, limit=40, min_coverage=0.9):
    """[(cosine, skill name)] for the skills closest in meaning to the text, best first; [] when meaning search is off,
    no model answers, or less than `min_coverage` of the catalog is embedded (run `sfp_embed.py build`)."""
    if not enabled() or not (text or '').strip():
        return []
    ep = endpoint_cached()
    if not ep:
        return []
    names, vecs, exvecs = _index(ep['model'])
    if not names or len(names) < min_coverage * len(core.CATALOG['skills']):
        return []
    try:
        q = _query_vector(ep['base_url'], ep['model'], text.strip()[:2000])
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        _ENDPOINT['checked'] = 0.0   # look for the runtime again next time
        return []
    dot = lambda v: sum(map(operator.mul, q, v))
    scored = []
    for n, v, ex in zip(names, vecs, exvecs):
        s = dot(v)
        if ex:
            s = (1 - EXAMPLE_WEIGHT) * s + EXAMPLE_WEIGHT * max(dot(e) for e in ex)
        scored.append((s, n))
    scored.sort(reverse=True)
    return scored[:limit]


def status():
    ep = find_endpoint()
    out = {'enabled': enabled(), 'endpoint': ep, 'skills': len(core.CATALOG['skills'])}
    if ep:
        names, _, exvecs = _index(ep['model'])
        out['embedded'] = len(names)
        out['with_examples'] = sum(1 for e in exvecs if e)
        out['cache'] = cache_path(ep['model'])
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    sub.add_parser('build')
    q = sub.add_parser('query')
    q.add_argument('text')
    q.add_argument('--limit', type=int, default=8)
    a = ap.parse_args(argv)
    if a.cmd == 'status':
        print(json.dumps(status(), indent=1))
    elif a.cmd == 'build':
        t0 = time.time()
        try:
            n, total = build(progress=lambda d, t: print('  embedded %d/%d' % (d, t), file=sys.stderr))
        except (RuntimeError, OSError, ValueError) as e:
            print('error: %s' % e, file=sys.stderr)
            return 1
        print('%d skills embedded now, %d in the cache (%.0fs)' % (n, total, time.time() - t0))
    else:
        for cos, name in similar(a.text, a.limit, min_coverage=0.0):
            print('%.3f  %s' % (cos, name))
    return 0


if __name__ == '__main__':
    sys.exit(main())
