#!/usr/bin/env python3
"""SFP MCP server: a bridge between the SFP skill library and any MCP client.

Speaks the Model Context Protocol over stdio (newline-delimited JSON-RPC) using
only the Python standard library. It is read-only: it searches the skill
catalog, returns a skill's SKILL.md and bundled files on demand, and runs the
bundled free-API search. An IDE or agent that has MCP but no skills folder can
use every skill without installing it.

Tools
  search_skills    find skills by task or keyword
  get_skill        the full SKILL.md of one skill, plus the files it bundles
  read_skill_file  one bundled file (reference docs, scripts) of a skill
  list_categories  categories, skill counts and install presets
  find_api         search about 2,100 free public APIs
  install_command  the command that installs categories or a preset
Resources
  sfp://skill/{name}   a skill's SKILL.md      sfp://catalog   the category summary
Prompts
  use_skill, find_skill_for

Run:  python3 mcp/sfp_mcp.py          (an MCP client starts it; it talks on stdin/stdout)
Env:  SFP_ROOT=/path/to/SFP           (only if the server is not inside the SFP checkout)
"""
import json
import math
import os
import re
import subprocess
import sys

SERVER_NAME = 'sfp'
SERVER_VERSION = '1.0.0'
SUPPORTED_PROTOCOLS = ['2025-06-18', '2025-03-26', '2024-11-05']
MAX_FILE_BYTES = 400000
MAX_LISTED_FILES = 200
MAX_RESULTS = 50


def find_root():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [os.environ.get('SFP_ROOT'), here]
    pointer = os.path.join(os.path.expanduser('~'), '.sfp', 'root')
    if os.path.isfile(pointer):
        candidates.append(open(pointer, encoding='utf-8').read().strip())
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, 'catalog.json')):
            return os.path.abspath(c)
    raise SystemExit('sfp-mcp: cannot find the SFP checkout (catalog.json). Set SFP_ROOT.')


ROOT = find_root()
CATALOG = json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))
SKILLS = {s['name']: s for s in CATALOG['skills']}


def log(msg):
    sys.stderr.write('sfp-mcp: %s\n' % msg)
    sys.stderr.flush()


# ---------------------------------------------------------------- skill access

def skill_dir(name):
    entry = SKILLS[name]
    path = os.path.realpath(os.path.join(ROOT, entry['path']))
    plugins = os.path.realpath(os.path.join(ROOT, 'plugins'))
    if not path.startswith(plugins + os.sep):
        raise ValueError('skill path escapes the plugins folder')
    return path


def resolve_name(name):
    """Return the skill name for an exact (case-insensitive) match, else None."""
    name = (name or '').strip().lower()
    if name in SKILLS:
        return name
    for n in SKILLS:
        if n.lower() == name:
            return n
    return None


STOP = frozenset('a an the and or of to in on at by for with from into onto up out my our your its it is are be do does how what '
                 'which that this these those i me we you can could should would will please need want make'.split())


def stem(w):
    for suf in ('ing', 'ed', 'es', 's'):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and not w.endswith('ss'):
            w = w[:-len(suf)]
            break
    if len(w) > 4 and w.endswith('e'):  # scrape, scraping and scraped all become scrap
        w = w[:-1]
    return w


# Names whose symbols would otherwise be thrown away by the word splitter.
ALIASES = (('c++', ' cpp '), ('c#', ' csharp '), ('f#', ' fsharp '), ('.net', ' dotnet '),
           ('node.js', ' nodejs '), ('next.js', ' nextjs '), ('nuxt.js', ' nuxtjs '))


def raw_words(text):
    text = (text or '').lower()
    for src, dst in ALIASES:
        text = text.replace(src, dst)
    return [t for t in re.split(r'[^a-z0-9]+', text) if len(t) > 1]


def tokens(text):
    """Search terms: lower-case words without filler, reduced to their stem."""
    return [stem(t) for t in raw_words(text) if t not in STOP]


def build_index():
    docs, df = [], {}
    for s in CATALOG['skills']:
        name = set(tokens(s['name'].replace('-', ' ')))
        desc = {}
        for w in tokens(s['description']):
            desc[w] = desc.get(w, 0) + 1
        cat = set(tokens(s['category'].replace('-', ' ')))
        docs.append((s, name, desc, cat))
        for w in name | set(desc) | cat:
            df[w] = df.get(w, 0) + 1
    return docs, df


INDEX, DF = build_index()


def search(query, category=None, limit=10):
    words = list(dict.fromkeys(tokens(query)))
    if not words:
        return []
    n = len(INDEX)
    idf = {w: math.log(1 + n / (1 + DF.get(w, 0))) for w in words}
    hits = []
    for s, name, desc, cat in INDEX:
        if category and s['category'] != category:
            continue
        score, matched = 0.0, 0
        for w in words:
            part = 0.0
            if w in name:
                part += 3.0 * idf[w]
            if w in desc:
                part += idf[w] * (1 + min(0.5, 0.1 * (desc[w] - 1)))
            if w in cat:
                part += 0.4 * idf[w]
            if part:
                matched += 1
                score += part
        if score:
            score *= 0.4 + 0.6 * matched / len(words)  # a skill that covers more of the task ranks higher
            if set(words) == name:
                score *= 1.5
            hits.append((score, s))
    hits.sort(key=lambda h: (-h[0], h[1]['name']))
    return [h[1] for h in hits[:max(1, min(limit, MAX_RESULTS))]]


def brief(s, desc_len=240):
    d = s['description']
    return {'name': s['name'], 'category': s['category'],
            'description': d if len(d) <= desc_len else d[:desc_len - 3] + '...'}


def list_files(base):
    out = []
    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if x not in ('node_modules', '__pycache__', '.git'))
        for f in sorted(files):
            out.append(os.path.relpath(os.path.join(d, f), base).replace(os.sep, '/'))
            if len(out) >= MAX_LISTED_FILES:
                return out
    return out


def read_text(path):
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        data = f.read(MAX_FILE_BYTES)
    if b'\x00' in data[:2048]:
        raise ValueError('binary file; only text files can be read')
    text = data.decode('utf-8', errors='replace')
    if size > MAX_FILE_BYTES:
        text += '\n\n[truncated: %d bytes, showing the first %d]' % (size, MAX_FILE_BYTES)
    return text


# ----------------------------------------------------------------------- tools

def tool_search_skills(a):
    query = a.get('query', '')
    cat = a.get('category')
    limit = int(a.get('limit', 10))
    if not tokens(query) and not cat:
        raise ValueError('give a query (words from the task) or a category')
    if cat and cat not in CATALOG['categories']:
        raise ValueError('unknown category %r. Categories: %s' % (cat, ', '.join(CATALOG['categories'])))
    if tokens(query):
        hits = search(query, cat, limit)
    else:
        hits = [s for s in CATALOG['skills'] if s['category'] == cat][:max(1, min(limit, MAX_RESULTS))]
    return json.dumps({'count': len(hits), 'skills': [brief(s) for s in hits],
                       'next': 'Call get_skill with a name to read the full instructions.'}, indent=1)


def tool_get_skill(a):
    name = resolve_name(a.get('name'))
    if not name:
        near = [s['name'] for s in search(a.get('name', ''), limit=5)]
        raise ValueError('no skill named %r.%s' % (a.get('name'), (' Closest: %s.' % ', '.join(near)) if near else ''))
    base = skill_dir(name)
    entry = SKILLS[name]
    files = [f for f in list_files(base) if f != 'SKILL.md']
    head = ['# Skill: %s' % name,
            'Category: %s  |  Source: %s  |  License: %s' % (entry['category'], entry['source'], entry['license'] or 'see its LICENSE'), '']
    if files:
        head.append('Bundled files (read one with read_skill_file; paths in the skill are relative to its folder):')
        head += ['- %s' % f for f in files[:60]]
        if len(files) > 60:
            head.append('- ... and %d more' % (len(files) - 60))
        head.append('')
    head += ['---', '']
    return '\n'.join(head) + read_text(os.path.join(base, 'SKILL.md'))


def tool_read_skill_file(a):
    name = resolve_name(a.get('name'))
    if not name:
        raise ValueError('no skill named %r' % a.get('name'))
    rel = (a.get('path') or '').replace('\\', '/').lstrip('/')
    if not rel:
        raise ValueError('give the file path relative to the skill folder, for example reference/index.md')
    base = skill_dir(name)
    target = os.path.realpath(os.path.join(base, rel))
    if not (target == base or target.startswith(base + os.sep)):
        raise ValueError('path is outside the skill folder')
    if not os.path.isfile(target):
        raise ValueError('no such file in %s: %s' % (name, rel))
    return read_text(target)


def presets():
    p = dict(CATALOG['profiles'])
    p['everything'] = 'all categories'
    return p


def tool_list_categories(a):
    cats = [{'category': n, 'skills': v['skills'] or 'plugin', 'description': v['description']}
            for n, v in CATALOG['categories'].items()]
    return json.dumps({'total_skills': len(CATALOG['skills']), 'categories': cats, 'presets': presets()}, indent=1)


def tool_find_api(a):
    script = os.path.join(ROOT, 'plugins', 'data-apis', 'skills', 'public-apis', 'scripts', 'find_api.py')
    if not os.path.isfile(script):
        raise ValueError('the public-apis skill is not in this checkout')
    cmd = [sys.executable, '-I', script, '--json', '--limit', str(max(1, min(int(a.get('limit', 10)), 50)))]
    for opt in ('category', 'auth', 'cors', 'https'):
        if a.get(opt):
            cmd += ['--' + opt, str(a[opt])]
    cmd += raw_words(a.get('query', ''))
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if done.returncode != 0:
        raise ValueError(done.stderr.strip() or 'find_api failed')
    return done.stdout.strip() or '[]'


def tool_install_command(a):
    cats = [c.strip() for c in (a.get('categories') or '').split(',') if c.strip()]
    profile = a.get('profile')
    tools = a.get('tools')
    for c in cats:
        if c not in CATALOG['categories']:
            raise ValueError('unknown category %r' % c)
    if profile and profile not in presets():
        raise ValueError('unknown preset %r. Presets: %s' % (profile, ', '.join(presets())))
    flags = ''
    if tools:
        flags += ' --tools %s' % tools
    if cats:
        flags += ' --categories %s' % ','.join(cats)
    elif profile:
        flags += ' --profile %s' % profile
    base = 'https://raw.githubusercontent.com/siddu1004/SFP/main'
    unix = 'curl -fsSL %s/get.sh | sh' % base + (' -s --%s' % flags if flags else '')
    win = '& ([scriptblock]::Create((irm %s/get.ps1)))' % base + flags
    out = ['macOS and Linux:\n  ' + unix, 'Windows PowerShell:\n  ' + win]
    if cats and (not tools or 'claude' in tools):
        out.append('Claude Code:\n' + '\n'.join('  /plugin install %s@sfp' % c for c in cats))
    return '\n\n'.join(out)


TOOLS = [
    {'name': 'search_skills',
     'description': 'Search the SFP skill library by task or keyword. Returns matching skills with their category and a short description. Use first when a task might have a matching skill, then call get_skill.',
     'inputSchema': {'type': 'object', 'properties': {
         'query': {'type': 'string', 'description': 'Words from the task, e.g. "postgres migration" or "react animation".'},
         'category': {'type': 'string', 'description': 'Optional category to restrict to, e.g. frontend, backend, security.'},
         'limit': {'type': 'integer', 'description': 'Maximum results (default 10, max 50).'}}},
     'fn': tool_search_skills},
    {'name': 'get_skill',
     'description': 'Get the full instructions (SKILL.md) of one SFP skill by name, plus the list of files it bundles. Follow the returned instructions for the task. Skill-relative paths resolve against the skill folder; read them with read_skill_file.',
     'inputSchema': {'type': 'object', 'properties': {'name': {'type': 'string', 'description': 'Exact skill name, e.g. impeccable.'}}, 'required': ['name']},
     'fn': tool_get_skill},
    {'name': 'read_skill_file',
     'description': 'Read one text file bundled with a skill (a reference doc, template or script), by path relative to the skill folder.',
     'inputSchema': {'type': 'object', 'properties': {
         'name': {'type': 'string', 'description': 'Skill name.'},
         'path': {'type': 'string', 'description': 'File path inside the skill, e.g. reference/audit.md.'}}, 'required': ['name', 'path']},
     'fn': tool_read_skill_file},
    {'name': 'list_categories',
     'description': 'List every SFP category with its skill count and description, and the install presets.',
     'inputSchema': {'type': 'object', 'properties': {}},
     'fn': tool_list_categories},
    {'name': 'find_api',
     'description': 'Search a bundled list of about 2,100 free public APIs. Filter by auth (none, apiKey, OAuth), CORS, HTTPS and category. Returns name, link, description, auth, https and cors for each.',
     'inputSchema': {'type': 'object', 'properties': {
         'query': {'type': 'string', 'description': 'Keywords, e.g. "weather forecast".'},
         'category': {'type': 'string', 'description': 'Category or part of one, e.g. Finance.'},
         'auth': {'type': 'string', 'enum': ['none', 'apiKey', 'OAuth', 'any']},
         'cors': {'type': 'string', 'enum': ['yes', 'no', 'unknown', 'any']},
         'https': {'type': 'string', 'enum': ['yes', 'no', 'any']},
         'limit': {'type': 'integer'}}},
     'fn': tool_find_api},
    {'name': 'install_command',
     'description': 'Return the command that installs SFP categories or a preset into an IDE, so the user can keep a skill permanently instead of fetching it on demand.',
     'inputSchema': {'type': 'object', 'properties': {
         'categories': {'type': 'string', 'description': 'Comma-separated categories, e.g. frontend,security.'},
         'profile': {'type': 'string', 'description': 'A preset: starter, frontend-dev, backend-dev, mobile-dev, agent-builder, everything.'},
         'tools': {'type': 'string', 'description': 'Comma-separated IDE ids, e.g. cursor,codex.'}}},
     'fn': tool_install_command},
]
TOOL_INDEX = {t['name']: t for t in TOOLS}
for _t in TOOLS:
    _t['annotations'] = {'readOnlyHint': True, 'openWorldHint': False}

# ------------------------------------------------------------ resources/prompts

SKILL_URI = re.compile(r'^sfp://skill/([A-Za-z0-9._-]+)$')


def resources_list():
    items = [{'uri': 'sfp://catalog', 'name': 'SFP catalog', 'mimeType': 'application/json',
              'description': 'Categories, skill counts and install presets.'}]
    for s in CATALOG['skills']:
        items.append({'uri': 'sfp://skill/%s' % s['name'], 'name': s['name'], 'mimeType': 'text/markdown',
                      'description': brief(s, 160)['description']})
    return items


def resource_read(uri):
    if uri == 'sfp://catalog':
        return {'uri': uri, 'mimeType': 'application/json', 'text': tool_list_categories({})}
    m = SKILL_URI.match(uri)
    if m and resolve_name(m.group(1)):
        name = resolve_name(m.group(1))
        return {'uri': uri, 'mimeType': 'text/markdown', 'text': read_text(os.path.join(skill_dir(name), 'SKILL.md'))}
    raise KeyError(uri)


PROMPTS = [
    {'name': 'use_skill', 'description': 'Load one SFP skill and apply it to a task.',
     'arguments': [{'name': 'name', 'description': 'Skill name', 'required': True},
                   {'name': 'task', 'description': 'What to do with it', 'required': False}]},
    {'name': 'find_skill_for', 'description': 'Find the best SFP skill for a task, then use it.',
     'arguments': [{'name': 'task', 'description': 'The task', 'required': True}]},
]


def prompt_get(name, args):
    args = args or {}
    if name == 'use_skill':
        text = tool_get_skill({'name': args.get('name')})
        task = args.get('task')
        body = 'Follow this SFP skill' + (' to do the following: %s' % task if task else '') + '.\n\n' + text
        desc = PROMPTS[0]['description']
    elif name == 'find_skill_for':
        task = args.get('task', '')
        top = search(task, limit=5)
        lines = '\n'.join('- %s (%s): %s' % (s['name'], s['category'], brief(s, 140)['description']) for s in top) or '- no close match'
        body = ('Task: %s\n\nCandidate SFP skills:\n%s\n\nPick the best one, call get_skill for it, '
                'and follow it. If none fits, say so and do the task normally.' % (task, lines))
        desc = PROMPTS[1]['description']
    else:
        raise KeyError(name)
    return {'description': desc, 'messages': [{'role': 'user', 'content': {'type': 'text', 'text': body}}]}


# --------------------------------------------------------------------- JSON-RPC

def ok(rid, result):
    return {'jsonrpc': '2.0', 'id': rid, 'result': result}


def err(rid, code, message):
    return {'jsonrpc': '2.0', 'id': rid, 'error': {'code': code, 'message': message}}


def handle(msg):
    method, rid, params = msg.get('method'), msg.get('id'), msg.get('params') or {}
    if method is None or rid is None:
        return None  # a client response, or a notification such as initialized
    try:
        if method == 'initialize':
            wanted = params.get('protocolVersion')
            version = wanted if wanted in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
            n_cats = len([c for c in CATALOG['categories'].values() if c['skills']])
            return ok(rid, {
                'protocolVersion': version,
                'capabilities': {'tools': {'listChanged': False},
                                 'resources': {'listChanged': False, 'subscribe': False},
                                 'prompts': {'listChanged': False}},
                'serverInfo': {'name': SERVER_NAME, 'version': SERVER_VERSION},
                'instructions': 'SFP skill library: %d skills in %d categories. Call search_skills with words from the task, '
                                'then get_skill and follow it. Use find_api for free public APIs.' % (len(SKILLS), n_cats)})
        if method == 'ping':
            return ok(rid, {})
        if method == 'tools/list':
            return ok(rid, {'tools': [{k: v for k, v in t.items() if k != 'fn'} for t in TOOLS]})
        if method == 'tools/call':
            tool = TOOL_INDEX.get(params.get('name'))
            if not tool:
                return err(rid, -32602, 'unknown tool %r' % params.get('name'))
            try:
                text = tool['fn'](params.get('arguments') or {})
                return ok(rid, {'content': [{'type': 'text', 'text': text}], 'isError': False})
            except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as e:
                return ok(rid, {'content': [{'type': 'text', 'text': 'Error: %s' % e}], 'isError': True})
        if method == 'resources/list':
            return ok(rid, {'resources': resources_list()})
        if method == 'resources/templates/list':
            return ok(rid, {'resourceTemplates': [{'uriTemplate': 'sfp://skill/{name}', 'name': 'SFP skill',
                                                   'description': "A skill's SKILL.md by name.", 'mimeType': 'text/markdown'}]})
        if method == 'resources/read':
            try:
                return ok(rid, {'contents': [resource_read(params.get('uri', ''))]})
            except KeyError:
                return err(rid, -32002, 'resource not found: %s' % params.get('uri'))
        if method == 'prompts/list':
            return ok(rid, {'prompts': PROMPTS})
        if method == 'prompts/get':
            try:
                return ok(rid, prompt_get(params.get('name'), params.get('arguments')))
            except KeyError:
                return err(rid, -32602, 'unknown prompt %r' % params.get('name'))
            except ValueError as e:
                return err(rid, -32602, str(e))
        return err(rid, -32601, 'method not found: %s' % method)
    except Exception as e:  # one bad request must not kill the server
        log('internal error in %s: %r' % (method, e))
        return err(rid, -32603, 'internal error')


def main():
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8')
    log('ready: %d skills from %s' % (len(SKILLS), ROOT))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            sys.stdout.write(json.dumps(err(None, -32700, 'parse error')) + '\n')
            sys.stdout.flush()
            continue
        reply = handle(msg) if isinstance(msg, dict) else err(None, -32600, 'batch requests are not supported')
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + '\n')
            sys.stdout.flush()


if __name__ == '__main__':
    main()
