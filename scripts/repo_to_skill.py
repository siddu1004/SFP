#!/usr/bin/env python3
"""Turn a Git repository (URL, owner/repo, or a folder) into an agent skill.

  python3 scripts/repo_to_skill.py <repo> [--name N] [--category C] [--dest DIR] [--install TOOL[,TOOL]] [--register] [--json]

The skill is written to <data folder>/skills/<name>/SKILL.md (or --dest) and, with --install, copied into the skills
folder of each tool you name (claude, codex, cursor, gemini, antigravity, ...). It is written from the repository's own
README: what it is, how to install it, the commands it documents and the environment variables it reads. If a local
model is running (Ollama, LM Studio, llama.cpp, Jan, vLLM, or the SFP router) the model writes it instead, and its answer
is used only when it has a valid header. Nothing in the SFP checkout is changed unless you pass --register, which adds the
skill to categories.json for the next sync. Standard library only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
CATEGORIES_FILE = os.path.join(ROOT, 'categories.json')
TEMPLATES_DIR = os.path.join(ROOT, 'templates')

CATEGORY_KEYWORDS = {
    'frontend': ['react', 'vue', 'svelte', 'css', 'html', 'tailwind', 'nextjs', 'vite', 'ui', 'component', 'animation', 'dom'],
    'backend': ['django', 'fastapi', 'flask', 'express', 'spring', 'rails', 'nestjs', 'postgres', 'sql', 'orm', 'database', 'sqlite', 'mongodb'],
    'devops': ['docker', 'kubernetes', 'k8s', 'terraform', 'ci/cd', 'github actions', 'deploy', 'nginx', 'helm', 'ansible'],
    'security': ['pentest', 'vulnerability', 'auth', 'oauth', 'jwt', 'owasp', 'cipher', 'crypto', 'security', 'exploit', 'audit'],
    'ai-ml': ['pytorch', 'tensorflow', 'llm', 'transformer', 'huggingface', 'model', 'rag', 'embedding', 'agent', 'neural', 'inference'],
    'mobile': ['android', 'ios', 'flutter', 'react native', 'swift', 'kotlin', 'mobile'],
    'data-apis': ['api', 'scraper', 'crawler', 'rest', 'graphql', 'dataset', 'http', 'client'],
    'languages': ['golang', 'rust', 'python', 'typescript', 'cpp', 'csharp', 'compiler', 'parser', 'syntax'],
    'testing-quality': ['test', 'pytest', 'jest', 'mock', 'tdd', 'e2e', 'cypress', 'playwright', 'benchmark', 'assert'],
}
INSTALL_HEADS = re.compile(r'install|setup|set up|getting started|quick ?start|requirements', re.I)
USAGE_HEADS = re.compile(r'usage|example|command|cli|api|how to|guide|tutorial|configur', re.I)
ENV_RX = re.compile(r'\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b')


def slugify(text):
    text = re.sub(r'[^a-z0-9\-]+', '-', text.lower().strip())
    return re.sub(r'-{2,}', '-', text).strip('-') or 'skill'


def data_dir():
    return os.environ.get('SFP_DATA_DIR') or os.path.join(os.path.expanduser('~'), '.sfp')


def clone_or_read(source):
    """(path, is_temporary) for a remote git URL, an owner/repo name or a local folder."""
    if os.path.isdir(source):
        return os.path.abspath(source), False
    tmp_dir = tempfile.mkdtemp(prefix='sfp_repo_')
    url = source if source.startswith(('http://', 'https://', 'git@')) else 'https://github.com/%s.git' % source
    res = subprocess.run(['git', 'clone', '--depth', '1', '--', url, tmp_dir], capture_output=True, text=True)
    if res.returncode != 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError('Could not clone %s: %s' % (url, res.stderr.strip()[:300]))
    return tmp_dir, True


def extract_context(repo_dir, max_chars=6000):
    """(context, readme): the README and the first manifest, trimmed, plus a listing of the top-level files."""
    readme_text = ''
    for name in ('README.md', 'README.rst', 'README.txt', 'readme.md', 'Readme.md'):
        p = os.path.join(repo_dir, name)
        if os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as f:
                    readme_text = f.read()
                break
            except OSError:
                pass
    manifest = ''
    for m in ('package.json', 'pyproject.toml', 'Cargo.toml', 'go.mod', 'setup.py'):
        p = os.path.join(repo_dir, m)
        if os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as f:
                    manifest = 'Manifest (%s):\n%s' % (m, f.read(1200))
                break
            except OSError:
                pass
    try:
        listing = 'Files: ' + ', '.join(sorted(n for n in os.listdir(repo_dir) if not n.startswith('.'))[:40])
    except OSError:
        listing = ''
    context = '\n\n'.join(x for x in (readme_text[:max_chars], manifest, listing) if x)
    return context[:max_chars + 2000], readme_text


def infer_category(name, context, custom=None):
    if custom:
        return custom
    text = (name + ' ' + context).lower()
    scores = {c: sum(1 for kw in kws if kw in text) for c, kws in CATEGORY_KEYWORDS.items()}
    scores = {c: n for c, n in scores.items() if n > 0}
    return max(scores, key=scores.get) if scores else 'engineering'


# ---- writing the skill with a local model, when there is one -------------------------------------------------

def _chat(base_url, model, prompt, timeout):
    payload = {'model': model, 'temperature': 0.2, 'max_tokens': 2048, 'messages': [
        {'role': 'system', 'content': 'You write agent skills as markdown with YAML frontmatter. Output only the markdown.'},
        {'role': 'user', 'content': prompt}]}
    req = urllib.request.Request(base_url.rstrip('/') + '/chat/completions', json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())['choices'][0]['message']['content'].strip()


def valid_skill(text, name):
    """The model's answer is used only if it is a skill with a header that names it and says when to use it."""
    text = re.sub(r'^```(?:markdown|md)?\s*|\s*```$', '', text.strip()).strip()
    m = re.match(r'---\s*\n(.*?)\n---\s*\n', text, re.S)
    if not m or not re.search(r'^name:\s*\S', m.group(1), re.M) or not re.search(r'^description:\s*\S', m.group(1), re.M):
        return None
    header = re.sub(r'^name:.*$', 'name: ' + name, m.group(1), count=1, flags=re.M)
    return '---\n%s\n---\n%s' % (header, text[m.end():])


def query_local_llm(prompt, name='skill', runtimes=None, timeout=40):
    """Ask the strongest local model (found the way the SFP router finds them), or the SFP router itself if it is running."""
    try:
        import sfp_route
    except ImportError:
        return None
    candidates = []
    try:
        with urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=0.5):
            candidates.append(('http://127.0.0.1:8787/v1', 'sfp/heavy'))
    except OSError:
        pass
    for f in sfp_route.discover(runtimes, timeout=0.6):
        best = max(f['models'], key=sfp_route.strength_of)
        candidates.append((f['base_url'], best))
    for base, model in candidates:
        try:
            out = valid_skill(_chat(base, model, prompt, timeout), name)
        except (OSError, ValueError, KeyError, IndexError):
            continue
        if out:
            return out
    return None


# ---- writing it from the README ------------------------------------------------------------------------------

def sections(readme):
    """[(heading, body)] split on markdown headings; the text before the first heading has heading ''."""
    parts, head, buf = [], '', []
    for line in readme.splitlines():
        m = re.match(r'^\s{0,3}#{1,4}\s+(.*?)\s*#*\s*$', line)
        if m and not line.strip().startswith('#!'):
            parts.append((head, '\n'.join(buf)))
            head, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    parts.append((head, '\n'.join(buf)))
    return parts


def code_blocks(text):
    return [b.strip('\n') for b in re.findall(r'```[a-zA-Z0-9_+-]*\n(.*?)```', text, re.S) if b.strip()]


def commands_in(blocks, limit=8):
    out = []
    for b in blocks:
        for line in b.splitlines():
            line = line.strip().lstrip('$ ').rstrip()
            if line and not line.startswith(('#', '//')) and len(line) < 160 and line not in out:
                out.append(line)
    return out[:limit]


def summary_of(readme, fallback):
    body = re.sub(r'```.*?```', '', readme, flags=re.S)
    body = re.sub(r'<[^>]+>|!\[[^\]]*\]\([^)]*\)', '', body)
    for para in re.split(r'\n\s*\n', body):
        text = ' '.join(l.strip() for l in para.splitlines() if not l.strip().startswith(('#', '|', '[!', '>', '-', '*'))).strip()
        text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
        if len(text) > 30 and not text.lower().startswith(('table of contents', 'license')):
            return re.split(r'(?<=[.!?])\s', text)[0][:240].rstrip('.')
    return fallback


def distill_markdown(skill_name, category, context, readme):
    """The SKILL.md text: the local model's if one answers well, otherwise written from the README."""
    prompt = ('Convert this repository into an agent skill.\nSkill name: %s\nCategory: %s\n\n%s\n\nWrite: YAML frontmatter with name and a '
              'description that says when to use it ("Use when ..."), then sections When to Use, Quickstart (the real commands), '
              'Patterns, and Pitfalls. Use only facts from the text above.' % (skill_name, category, context[:4500]))
    llm = query_local_llm(prompt, skill_name)
    if llm:
        return llm
    parts = sections(readme)
    title = next((h for h, _ in parts if h), skill_name)
    summary = summary_of(readme, 'Workflows for %s' % skill_name)
    install_blocks = [b for h, body in parts if INSTALL_HEADS.search(h) for b in code_blocks(body)]
    usage_blocks = [b for h, body in parts if USAGE_HEADS.search(h) and not INSTALL_HEADS.search(h) for b in code_blocks(body)]
    install = commands_in(install_blocks) or commands_in(code_blocks(readme), 4)
    usage = [c for c in commands_in(usage_blocks, 12) if c not in install][:8]
    env = [v for v in dict.fromkeys(ENV_RX.findall(readme)) if v not in ('README', 'TODO', 'LICENSE')][:6]
    topics = [h for h, _ in parts if h and h.lower() != title.lower()
              and not re.search(r'licen[sc]e|contribut|acknowledg|changelog|table of contents|badge|star', h, re.I)][:8]
    description = '%s. Use when working with %s: setting it up, running its commands, or debugging it.' % (summary, skill_name)
    out = ['---', 'name: %s' % skill_name, 'description: %s' % json.dumps(description, ensure_ascii=False), '---', '', '# %s' % skill_name,
           '', summary + '.', '', '## When to use']
    out += ['- Installing, configuring or upgrading %s.' % skill_name,
            '- Running the commands %s documents%s.' % (skill_name, ' (below)' if usage else ''),
            '- Diagnosing a problem with %s.' % skill_name]
    if install:
        out += ['', '## Quickstart', '```bash'] + install + ['```']
    if usage:
        out += ['', '## Commands', '```bash'] + usage + ['```']
    if env:
        out += ['', '## Configuration', 'The documentation mentions these environment variables:'] + ['- `%s`' % v for v in env]
    if topics:
        out += ['', '## What the documentation covers'] + ['- %s' % t for t in topics]
    out += ['', '## Notes', '- Written from the repository README. Read the README before relying on a command here.', '']
    return '\n'.join(out)


def register_skill_in_categories(skill_name, category, category_desc=None, categories_file=CATEGORIES_FILE):
    """Assign the skill to its category in categories.json, creating the category if needed (only with --register)."""
    if not os.path.isfile(categories_file):
        return
    with open(categories_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if category not in data.get('categories', {}):
        data.setdefault('categories', {})[category] = category_desc or 'Skills and workflows for %s.' % category
    data.setdefault('names', {})[skill_name] = category
    with open(categories_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def install_into(out_dir, skill_name, tools):
    """Copy the skill folder into each tool's skills folder; returns {tool: path}."""
    import install as sfp_install
    placed = {}
    for tool in tools:
        if tool not in sfp_install.TOOLS:
            raise ValueError('unknown tool %r (choose from %s)' % (tool, ', '.join(sorted(sfp_install.TOOLS))))
        dest = os.path.join(sfp_install.TOOLS[tool][2], skill_name)
        shutil.copytree(out_dir, dest, dirs_exist_ok=True)
        placed[tool] = dest
    return placed


def convert(repo_source, custom_name=None, custom_category=None, category_desc=None, dest=None, categories_file=CATEGORIES_FILE,
            register=False, install=()):
    """The whole job. Returns {skill_name, category, skill_path, status, installed, registered}."""
    base = custom_name or os.path.basename(repo_source.rstrip('/\\')).replace('.git', '')
    skill_name = slugify(base)
    repo_dir, is_tmp = clone_or_read(repo_source)
    try:
        context, readme = extract_context(repo_dir)
        category = infer_category(skill_name, context, custom=custom_category)
        skill_md = distill_markdown(skill_name, category, context, readme)
        out_dir = dest or os.path.join(data_dir(), 'skills', skill_name)
        os.makedirs(out_dir, exist_ok=True)
        skill_file = os.path.join(out_dir, 'SKILL.md')
        with open(skill_file, 'w', encoding='utf-8') as f:
            f.write(skill_md)
        if register:
            register_skill_in_categories(skill_name, category, category_desc=category_desc, categories_file=categories_file)
        installed = install_into(out_dir, skill_name, list(install)) if install else {}
        return {'skill_name': skill_name, 'category': category, 'skill_path': skill_file, 'status': 'ok', 'installed': installed,
                'registered': bool(register)}
    finally:
        if is_tmp:
            shutil.rmtree(repo_dir, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('repo', help='Git URL, owner/repo, or a local folder')
    ap.add_argument('--category', help='category name (inferred if omitted)')
    ap.add_argument('--name', help='skill name (taken from the repository name if omitted)')
    ap.add_argument('--desc', help='description, if the category is new')
    ap.add_argument('--dest', help='folder to write the skill to (default: <data folder>/skills/<name>)')
    ap.add_argument('--install', default='', help='comma-separated tools to copy the skill into, e.g. claude,antigravity')
    ap.add_argument('--register', action='store_true', help='add the skill to categories.json in this checkout')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        res = convert(args.repo, custom_name=args.name, custom_category=args.category, category_desc=args.desc, dest=args.dest,
                      register=args.register, install=[t for t in args.install.split(',') if t.strip()])
    except (RuntimeError, ValueError, OSError) as e:
        if args.json:
            print(json.dumps({'error': str(e), 'status': 'fail'}))
        else:
            print('fail: %s' % e, file=sys.stderr)
        raise SystemExit(1)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print("ok: created skill '%s' in category '%s'\n    %s" % (res['skill_name'], res['category'], res['skill_path']))
        for tool, path in res['installed'].items():
            print('    installed for %s: %s' % (tool, path))


if __name__ == '__main__':
    main()
