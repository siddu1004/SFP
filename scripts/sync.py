#!/usr/bin/env python3
"""Rebuild plugins/ from the source repos listed in sources.json.

Usage:
  python3 scripts/sync.py                 # shallow-clone each source into .cache/
  python3 scripts/sync.py --src-dir DIR   # use existing checkouts in DIR/<repo-name>
  python3 scripts/sync.py --report        # also list what each category got

Each skill lands in a category (categories.json rules), written to
plugins/<category>/skills/<skill>/. The sync also writes the Claude Code
marketplace, catalog.json, SKILLS.md and the router skill's index.
Everything it writes is generated: edit sources.json or categories.json.
"""
import argparse
import fnmatch
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORE = shutil.ignore_patterns('.git', '.github', 'node_modules', '__pycache__', '.DS_Store', 'bin')
MARKETPLACE = 'sfp'
VERSION = '3.15.0'
OUT = os.path.join(ROOT, 'plugins')


def frontmatter(text):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.S)
    return m.group(1) if m else ''


def field(fm, key):
    m = re.search(rf'^{key}:\s*(.*)$', fm, re.M)
    if not m:
        return ''
    value = m.group(1).strip()
    if value in ('>', '>-', '|', '|-'):
        lines = []
        for line in fm[m.end():].splitlines()[1:]:
            if line and not line[0].isspace():
                break
            lines.append(line.strip())
        value = ' '.join(l for l in lines if l)
    return value.strip('"\'')


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def rel(path, start):
    """A relative path with forward slashes, the same on every system. The catalog and the hashes must not
    depend on where the sync ran: a catalog written on Windows with backslashes breaks every other system."""
    return os.path.relpath(path, start).replace(os.sep, '/')


def tree_hash(path):
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(path)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(d, f)
            if os.path.isfile(p):
                h.update(rel(p, path).encode())
                with open(p, 'rb') as fh:
                    h.update(fh.read())
    return h.hexdigest()


def rename_skill(skill_dir, new_name):
    p = os.path.join(skill_dir, 'SKILL.md')
    text = open(p, encoding='utf-8', errors='replace').read()
    if re.search(r'^name:.*$', frontmatter(text), re.M):
        text = re.sub(r'^name:.*$', f'name: {new_name}', text, count=1, flags=re.M)
    else:
        text = re.sub(r'^---\s*\n', f'---\nname: {new_name}\n', text, count=1)
    open(p, 'w', encoding='utf-8').write(text)


def checkout(repo, src_dir, cache):
    name = repo.split('/')[1]
    safe_name = repo.replace('/', '__')
    if src_dir:
        if os.path.isdir(os.path.join(src_dir, safe_name)):
            return os.path.join(src_dir, safe_name)
        if os.path.isdir(os.path.join(src_dir, name)):
            return os.path.join(src_dir, name)
    dest = os.path.join(cache, safe_name)
    if not os.path.isdir(dest):
        env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
        subprocess.run(['git', 'clone', '-q', '--depth', '1', '--no-tags', '--single-branch', f'https://github.com/{repo}.git', dest], check=True, env=env)
    return dest


def copy_skill(src, dest):
    shutil.copytree(src, dest, ignore=IGNORE, symlinks=False, ignore_dangling_symlinks=True)


def load_apps():
    with open(os.path.join(ROOT, 'apps', 'apps.json'), encoding='utf-8') as f:
        return json.load(f)


def app_for(apps, name, repo):
    """The program (apps/apps.json) that a skill is a guide to, if there is one."""
    return next((k for k, a in apps.items() if repo in a.get('sources', []) or name in a.get('names', [])), None)


def attach_app(dest, key, app):
    """Put the setup engine and this program's entry inside the skill, and tell the agent about it first thing."""
    scripts = os.path.join(dest, 'scripts')
    os.makedirs(scripts, exist_ok=True)
    shutil.copy(os.path.join(ROOT, 'apps', 'sfp_app.py'), os.path.join(scripts, 'sfp_app.py'))
    with open(os.path.join(scripts, 'app.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(app, id=key), f, indent=2, ensure_ascii=False)
        f.write('\n')
    p = os.path.join(dest, 'SKILL.md')
    text = open(p, encoding='utf-8', errors='replace').read()
    note = ('\n> **This skill needs %s, which is installed separately.** From this skill\'s folder, run '
            '`python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run '
            '`python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, '
            'and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.\n'
            % app['name'])
    m = re.match(r'^---\s*\n.*?\n---[ \t]*\n', text, re.S)
    text = (text[:m.end()] + note + text[m.end():]) if m else (note.lstrip() + '\n' + text)
    open(p, 'w', encoding='utf-8').write(text)


class Classifier:
    def __init__(self, cfg):
        self.names = cfg['names']
        self.patterns = [(c, re.compile(p)) for c, p in cfg['patterns']]
        self.known = set(cfg['categories'])

    def category(self, name, source):
        if name in self.names:
            cat = self.names[name]
        elif source.get('fixed'):
            cat = source['default']
        else:
            cat = next((c for c, rx in self.patterns if rx.search(name)), source['default'])
        if cat not in self.known:
            sys.exit(f'category {cat!r} (for {name}) is not defined in categories.json')
        return cat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', help='directory holding existing checkouts named after each repo')
    ap.add_argument('--report', action='store_true')
    args = ap.parse_args()

    cfg = json.load(open(os.path.join(ROOT, 'sources.json')))
    cats = json.load(open(os.path.join(ROOT, 'categories.json')))
    clf = Classifier(cats)
    cache = os.path.join(ROOT, '.cache')
    shutil.rmtree(OUT, ignore_errors=True)

    catalog, taken, licenses = [], {}, {}
    apps = load_apps()

    def add(skill_src, source, prefix, variants=None):
        text = open(os.path.join(skill_src, 'SKILL.md'), encoding='utf-8', errors='replace').read()
        fm = frontmatter(text)
        name = slug(field(fm, 'name') or os.path.basename(skill_src))
        npfx = source.get('name_prefix')
        if npfx and not name.startswith(tuple(source.get('name_prefix_skip', [npfx.rstrip('-')]))):
            name = slug(npfx + name)
        digest = tree_hash(skill_src)
        if name in taken:
            if taken[name] == digest:
                return
            name = slug(prefix + name)
            if name in taken:
                print(f'  ! skipped {skill_src}: name {name} still taken', file=sys.stderr)
                return
        taken[name] = digest
        cat = clf.category(name, source)
        dest = os.path.join(OUT, cat, 'skills', name)
        copy_skill(skill_src, dest)
        if field(fm, 'name') != name:
            rename_skill(dest, name)
        app_key = app_for(apps, name, source['repo'])
        if app_key:
            attach_app(dest, app_key, apps[app_key])
        entry = {
            'name': name, 'category': cat,
            'description': ' '.join(field(fm, 'description').split()),
            'source': source['repo'], 'license': source.get('license', ''),
            'path': rel(dest, ROOT), 'variants': {},
        }
        for tool, vsrc in (variants or {}).items():
            vdest = os.path.join(OUT, cat, 'variants', tool, name)
            copy_skill(vsrc, vdest)
            rename_skill(vdest, name)
            entry['variants'][tool] = rel(vdest, ROOT)
        if app_key:
            entry['app'] = app_key
        catalog.append(entry)
        licenses.setdefault(cat, set()).add(source['repo'])

    lic_by_repo = {}
    lock = {}
    for source in cfg['sources']:
        if 'local' in source:
            repo_dir = os.path.join(ROOT, source['local'])
        else:
            repo_dir = checkout(source['repo'], args.src_dir, cache)
            sha = subprocess.run(['git', '-C', repo_dir, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
            if sha:
                lock[source['repo']] = sha
        prefix = source.get('collision_prefix', source['default'] + '-')
        print(f"{source['repo']}")
        excludes = source.get('exclude', [])
        if 'template' in source:
            staged = os.path.join(cache, '_staged', os.path.basename(source['template']))
            shutil.rmtree(staged, ignore_errors=True)
            shutil.copytree(os.path.join(ROOT, source['template']), staged)
            for src_file, dest_file in source.get('files', {}).items():
                os.makedirs(os.path.dirname(os.path.join(staged, dest_file)), exist_ok=True)
                shutil.copy(os.path.join(repo_dir, src_file), os.path.join(staged, dest_file))
            if 'patch' in source:
                # The template carries a patch for this repo: it must apply to the commit being integrated.
                patch = os.path.join(ROOT, source['patch'])
                check = subprocess.run(['git', '-C', repo_dir, 'apply', '--ignore-space-change', '--ignore-whitespace', '--check', patch], capture_output=True, text=True)
                if check.returncode != 0:
                    sys.exit('%s: %s no longer applies to the upstream commit being integrated. Rebase the patch.\n%s'
                             % (source['repo'], source['patch'], check.stderr.strip()))
            sha = lock.get(source['repo'], '')
            for d, _dirs, files in os.walk(staged):
                for f in files:
                    p = os.path.join(d, f)
                    try:
                        txt = open(p, encoding='utf-8').read()
                    except (UnicodeDecodeError, OSError):
                        continue
                    if '@@COMMIT@@' in txt:
                        open(p, 'w', encoding='utf-8').write(txt.replace('@@COMMIT@@', sha))
            add(staged, source, prefix)
        for pattern in source.get('skills', []):
            for skill_src in sorted(glob.glob(os.path.join(repo_dir, pattern))):
                skill_src = os.path.normpath(skill_src)
                rel_src = rel(skill_src, repo_dir)
                if not os.path.isfile(os.path.join(skill_src, 'SKILL.md')):
                    continue
                if any(fnmatch.fnmatch(rel_src, e) for e in excludes):
                    continue
                variants = {t: os.path.join(repo_dir, p) for t, p in source.get('variants', {}).items()
                            if os.path.isfile(os.path.join(repo_dir, p, 'SKILL.md'))}
                add(skill_src, source, prefix, variants)
        lic = next((f for f in sorted(os.listdir(repo_dir)) if f.upper().startswith(('LICENSE', 'LICENCE'))), None)
        if lic:
            lic_by_repo[source['repo']] = os.path.join(repo_dir, lic)
        elif source.get('license'):
            fallback_lic = os.path.join(repo_dir, 'LICENSE')
            if not os.path.exists(fallback_lic):
                with open(fallback_lic, 'w', encoding='utf-8') as lf:
                    lf.write(f"{source['license']} License\n\nSource: https://github.com/{source['repo']}\n")
            lic_by_repo[source['repo']] = fallback_lic

    with open(os.path.join(ROOT, 'sources.lock.json'), 'w', encoding='utf-8') as f:
        json.dump(lock, f, indent=2, sort_keys=True)
        f.write('\n')

    # Copy each category's source licenses next to its skills.
    for cat, repos in licenses.items():
        for repo in sorted(repos):
            if repo in lic_by_repo and lic_by_repo[repo]:
                d = os.path.join(OUT, cat, 'LICENSES')
                os.makedirs(d, exist_ok=True)
                dest_lic = repo.replace('/', '-') + '.txt'
                shutil.copy(lic_by_repo[repo], os.path.join(d, dest_lic))

    # The router skill: a template plus a generated index of every other skill.
    router = os.path.join(OUT, 'sfp', 'skills', 'sfp')
    os.makedirs(os.path.dirname(router), exist_ok=True)
    shutil.copytree(os.path.join(ROOT, 'templates', 'sfp'), router)
    os.makedirs(os.path.join(router, 'scripts'), exist_ok=True)
    shutil.copy(os.path.join(ROOT, 'apps', 'sfp_app.py'), os.path.join(router, 'scripts', 'sfp_app.py'))
    shutil.copy(os.path.join(ROOT, 'apps', 'apps.json'), os.path.join(router, 'scripts', 'app.json'))
    os.makedirs(os.path.join(router, 'reference'), exist_ok=True)
    write_index(os.path.join(router, 'reference', 'index.md'), cats, cfg, catalog)
    catalog.append({
        'name': 'sfp', 'category': 'sfp',
        'description': ' '.join(field(frontmatter(open(os.path.join(router, 'SKILL.md'), encoding='utf-8').read()), 'description').split()),
        'source': 'siddu1004/SFP', 'license': '', 'path': rel(router, ROOT), 'variants': {},
    })
    # The selection skill: chooses which skills a task needs, in what order, and learns from feedback (mcp/sfp_hive.py).
    hive = os.path.join(OUT, 'sfp', 'skills', 'sfp-hive')
    shutil.copytree(os.path.join(ROOT, 'templates', 'sfp-hive'), hive)
    catalog.append({
        'name': 'sfp-hive', 'category': 'sfp',
        'description': ' '.join(field(frontmatter(open(os.path.join(hive, 'SKILL.md'), encoding='utf-8').read()), 'description').split()),
        'source': 'siddu1004/SFP', 'license': 'MIT', 'path': rel(hive, ROOT), 'variants': {},
    })

    write_manifests(cfg, cats, catalog)
    render_readme(cfg, cats, catalog)
    used = sorted({c['category'] for c in catalog})
    print(f'{len(catalog)} skills in {len(used)} categories')
    if args.report:
        for cat in used:
            names = [c['name'] for c in catalog if c['category'] == cat]
            print(f'\n{cat} ({len(names)}): ' + ', '.join(names))


def measure(cfg, cats, catalog):
    """Figures quoted in the README, computed from the real catalog so they cannot drift."""
    import importlib.util
    import statistics
    spec = importlib.util.spec_from_file_location('sfp_mcp_measure', os.path.join(ROOT, 'mcp', 'sfp_mcp.py'))
    mod = importlib.util.module_from_spec(spec)
    os.environ['SFP_ROOT'] = ROOT
    spec.loader.exec_module(mod)
    mod.write_index()  # the start-up cache for the search index; see load_index in mcp/sfp_mcp.py

    # Retrieval: does the right skill come back for a plain-language task?
    n = 0
    hits = {1: 0, 3: 0, 5: 0}
    for name in ('search_eval.json', 'search_holdout.json', 'search_fresh.json'):
        path = os.path.join(ROOT, 'tests', name)
        if not os.path.isfile(path):
            continue
        for case in json.load(open(path, encoding='utf-8')):
            want = {x for x in case['expect'] if x in mod.SKILLS}
            got = [s['name'] for s in mod.search(case['task'], limit=5)]
            n += 1
            for k in hits:
                if want & set(got[:k]):
                    hits[k] += 1

    # Context cost: what an agent carries per installed skill is its name and description (about 4 characters a token).
    def tok(s):
        return -(-(len(s['name']) + len(s['description']) + 12) // 4)

    by_cat = {}
    for s in catalog:
        by_cat.setdefault(s['category'], []).append(s)

    def cost(members):
        skills = [s for c in members for s in by_cat.get(c, [])]
        return len(skills), sum(tok(s) for s in skills)

    window = 200000
    rows = ['| What you install | Skills your agent can use | Skill descriptions it carries each session | Share of a 200k-token window |',
            '|---|---:|---:|---:|']
    sfp_n, sfp_t = cost(['sfp'])
    rows.append('| `sfp` and `sfp-hive` only (the rest on demand) | %d + all %d through them | about %s tokens | %.1f%% |'
                % (sfp_n, len(catalog) - sfp_n, format(sfp_t, ','), 100.0 * sfp_t / window))
    for name, members in cfg['profiles'].items():
        k, tk = cost(sorted(set(members) | {'sfp'}))
        rows.append('| `%s` preset | %d | about %s tokens | %.1f%% |' % (name, k, format(tk, ','), 100.0 * tk / window))
    all_cats = [c for c in by_cat]
    k, tk = cost(all_cats)
    rows.append('| `everything` | %d | about %s tokens | %.1f%% |' % (k, format(tk, ','), 100.0 * tk / window))

    # What one skill costs when it is actually used.
    sizes = []
    for s in catalog:
        f = os.path.join(ROOT, s['path'], 'SKILL.md')
        if os.path.isfile(f):
            sizes.append(os.path.getsize(f) // 4)
    sizes.sort()

    # The hive, scored against the earlier engine and plain search on the same tasks, and whether it learns.
    sys.modules['sfp_mcp'] = mod
    sys.path.insert(0, os.path.join(ROOT, 'mcp'))
    for stale in ('sfp_stack', 'sfp_hive', 'sfp_learn'):
        sys.modules.pop(stale, None)
    import sfp_hive as eng
    import sfp_learn as learn
    ev = eng.evaluate(os.path.join(ROOT, 'tests'))
    lc = learn.learning_curve(os.path.join(ROOT, 'tests'))
    for gone in ('sfp_mcp', 'sfp_stack', 'sfp_hive', 'sfp_learn'):
        sys.modules.pop(gone, None)

    def pct(x):
        return '%d%%' % round(100.0 * x)

    stack = {'RECIPES': str(len(eng.v1.RECIPES)), 'SEL_VERSION': eng.VERSION}
    for key in ('bench', 'proj', 'fresh'):
        k = key.upper()
        h, o, s = ev[key + '_select'], ev[key + '_v1'], ev[key + '_search']
        stack.update({
            k + '_N': str(h['n']), k + '_SEL': pct(h['hit']), k + '_V1': pct(o['hit']), k + '_SEARCH': pct(s['hit']),
            k + '_SEL_FIRST': pct(h['first']), k + '_V1_FIRST': pct(o['first']),
            k + '_SEL_SIZE': '%.1f' % h['size'], k + '_V1_SIZE': '%.1f' % o['size'],
            k + '_SEL_WRONG': str(h['wrong']), k + '_SEARCH_WRONG': str(s['wrong']),
        })
    for eng_name, label in (('select', 'SEL'), ('v1', 'V1'), ('search', 'SEARCH')):
        stack['WRONG_' + label] = str(sum(ev[k + '_' + eng_name]['wrong'] for k in ('bench', 'proj', 'fresh')))
    stack.update({
        'LC_TASKS': str(lc['tasks']), 'LC_FOLDS': str(lc['folds_total']),
        'LC_BASE': '%.1f%%' % (100 * lc['heldout_without_learning']), 'LC_NEW': '%.1f%%' % (100 * lc['heldout_with_learning']),
        'LC_GAIN': '%+.1f' % (100 * lc['gain']), 'LC_UP': str(lc['folds_improved']), 'LC_DOWN': str(lc['folds_worse']),
        'LC_FIXED': pct(lc['training_mistakes_fixed_on_retry'] or 0), 'LC_WORSE': str(lc['heldout_tasks_that_got_worse']),
        'LC_WRONG': str(lc['wrong_technology_stacks_heldout']),
    })
    # The same words in five different projects, as real output, so the README cannot drift from the engine.
    import tempfile
    hist = eng.History(eng.v1.RECIPES, [])
    same_rows = ['| Your project | The hive chooses |', '|---|---|']
    with tempfile.TemporaryDirectory() as tmp:
        homes = {}
        for fname in ('stack_eval.json', 'hive_heldout.json'):
            with open(os.path.join(ROOT, 'tests', fname), encoding='utf-8') as f:
                data = json.load(f)
            eng._projects(data, os.path.join(tmp, fname))
            homes.update({k: os.path.join(tmp, fname, k) for k in data['projects']})
        for label, key in (('Next.js', 'nextjs'), ('Rust', 'rust'), ('.NET', 'dotnet'), ('Flutter', 'flutter'), ('Django', 'django')):
            res = eng.select('write tests for the orders', homes[key], history=hist)
            same_rows.append('| %s | %s |' % (label, ', '.join('`%s`' % c['name'] for c in res['stack'])))
    stack['SAME_WORDS_TABLE'] = '\n'.join(same_rows)
    every = [ev[k + '_select'] for k in ('bench', 'proj', 'fresh')]
    n_all = sum(x['n'] for x in every)
    stack['SEL_TOKENS'] = format(int(round(sum(x['tokens'] * x['n'] for x in every) / n_all, -2)), ',')
    stack['SEL_MS'] = str(max(1, round(sum(x['ms'] * x['n'] for x in every) / n_all)))
    return dict(stack, **{
        'SEARCH_N': str(n),
        'SEARCH_TOP1': '%d%%' % round(100.0 * hits[1] / n) if n else 'n/a',
        'SEARCH_TOP3': '%d%%' % round(100.0 * hits[3] / n) if n else 'n/a',
        'SEARCH_TOP5': '%d%%' % round(100.0 * hits[5] / n) if n else 'n/a',
        'COST_TABLE': '\n'.join(rows),
        'BODY_MEDIAN': format(int(statistics.median(sizes)), ',') if sizes else 'n/a',
        'BODY_P90': format(sizes[int(len(sizes) * 0.9)], ',') if sizes else 'n/a',
        'SFP_TOKENS': format(sfp_t, ','),
        'RATIO': str(round(tk / sfp_t)) if sfp_t else 'n/a',
        'ALL_TOKENS': format(tk, ','),
        'ALL_PERCENT': '%d' % round(100.0 * tk / window),
    })


def render_readme(cfg, cats, catalog):
    """Fill templates/README.md.tpl from the catalog; write README.md and draw the banners."""
    tpl = os.path.join(ROOT, 'templates', 'README.md.tpl')
    if not os.path.isfile(tpl):
        return
    per_cat = {}
    for c in catalog:
        per_cat[c['category']] = per_cat.get(c['category'], 0) + 1
    total = len(catalog)
    repos = len({s['repo'] for s in cfg['sources']} | {e['app']['repo'] for e in cfg['externals'].values() if 'app' in e})

    rows = ['| Category | Skills | What is in it |', '|---|---:|---|']
    for cat, desc in cats['categories'].items():
        if per_cat.get(cat):
            rows.append(f'| `{cat}` | {per_cat[cat]} | {desc} |')
    for name, ext in cfg['externals'].items():
        rows.append(f"| `{name}` | plugin | {ext['description']} |")

    notes = cfg.get('profile_notes', {})
    prows = ['| Preset | Good for | Categories |', '|---|---|---|']
    for name, members in cfg['profiles'].items():
        prows.append(f"| `{name}` | {notes.get(name, '')} | " + ' '.join(f'`{m}`' for m in members) + ' |')
    prows.append(f"| `everything` | {notes.get('everything', '')} | all |")

    text = open(tpl, encoding='utf-8').read()
    values = {'TOTAL': str(total), 'NCATS': str(len(per_cat)), 'SOURCES': str(repos),
              'CATEGORY_TABLE': '\n'.join(rows), 'PRESET_TABLE': '\n'.join(prows)}
    values.update(measure(cfg, cats, catalog))
    for key in ('omniroute', 'claude-mem', 'strix'):
        values['APP_' + key.upper().replace('-', '_')] = str(sum(1 for c in catalog if c.get('app') == key))
    for key, value in values.items():
        text = text.replace('@@' + key + '@@', value)
    open(os.path.join(ROOT, 'README.md'), 'w', encoding='utf-8').write(text)

    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import banner
    banner.main()


def write_index(path, cats, cfg, catalog):
    lines = ['# SFP skill index', '',
             'Generated by `scripts/sync.py`. One line per skill: its name, then what it does. '
             'A skill lives at `plugins/<category>/skills/<name>/SKILL.md` in the SFP repo.', '']
    for cat, desc in cats['categories'].items():
        rows = [c for c in catalog if c['category'] == cat]
        ext = cfg['externals'].get(cat)
        if not rows and not ext:
            continue
        lines += [f'## {cat}', '', desc, '']
        if ext and not rows:
            lines += ['Runs from its own checkout; the installer sets it up (see the SFP README).', '']
        for c in rows:
            d = c['description']
            d = (d[:157] + '...') if len(d) > 160 else d
            lines.append(f"- `{c['name']}`: {d}")
        lines.append('')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines))


def write_manifests(cfg, cats, catalog):
    counts = {}
    for c in catalog:
        counts[c['category']] = counts.get(c['category'], 0) + 1

    plugins, meta = [], {}
    for cat, desc in cats['categories'].items():
        if cat in cfg['externals'] or not counts.get(cat):
            continue
        plugins.append({'name': cat, 'description': desc, 'category': 'skills', 'source': f'./plugins/{cat}'})
        meta[cat] = {'description': desc, 'skills': counts[cat]}
        d = os.path.join(OUT, cat, '.claude-plugin')
        os.makedirs(d, exist_ok=True)
        manifest = {'name': cat, 'version': VERSION, 'description': desc, 'author': {'name': 'siddu1004'},
                    'repository': 'https://github.com/siddu1004/SFP', 'license': 'MIT', 'skills': './skills/'}
        json.dump(manifest, open(os.path.join(d, 'plugin.json'), 'w'), indent=2)
        # The same plugin for other IDEs. Cursor and GitHub Copilot CLI read plugin.json at the plugin root;
        # Codex reads .codex-plugin/plugin.json.
        json.dump(manifest, open(os.path.join(OUT, cat, 'plugin.json'), 'w'), indent=2)
        os.makedirs(os.path.join(OUT, cat, '.codex-plugin'), exist_ok=True)
        json.dump(dict(manifest, interface={
            'displayName': 'SFP ' + cat, 'shortDescription': desc[:120], 'longDescription': desc,
            'developerName': 'siddu1004', 'category': 'Coding', 'capabilities': ['Interactive', 'Read', 'Write'],
            'websiteURL': 'https://github.com/siddu1004/SFP'}),
                  open(os.path.join(OUT, cat, '.codex-plugin', 'plugin.json'), 'w'), indent=2)
    for name, ext in cfg['externals'].items():
        plugins.append({'name': name, 'description': ext['description'], 'category': 'skills', 'source': ext['claude']})
        meta[name] = {k: v for k, v in ext.items() if k != 'claude'}
        meta[name]['skills'] = counts.get(name, 0)

    os.makedirs(os.path.join(ROOT, '.claude-plugin'), exist_ok=True)
    json.dump({
        '$schema': 'https://anthropic.com/claude-code/marketplace.schema.json',
        'name': MARKETPLACE,
        'owner': {'name': 'siddu1004'},
        'metadata': {'description': 'SFP, Skills for Productivity: %d agent skills sorted by what you build, plus a hive that picks the few each task needs for your project and learns from feedback. Installs into 16 IDEs and CLIs, and serves any MCP client.' % len(catalog)},
        'plugins': plugins,
    }, open(os.path.join(ROOT, '.claude-plugin', 'marketplace.json'), 'w'), indent=2)

    # Marketplaces for the other IDEs that have them, listing the same plugins (not Claude-only externals).
    local = [p for p in plugins if isinstance(p['source'], str)]
    os.makedirs(os.path.join(ROOT, '.cursor-plugin'), exist_ok=True)
    json.dump({'name': MARKETPLACE, 'owner': {'name': 'siddu1004'},
               'plugins': [{'name': p['name'], 'source': p['source'], 'description': p['description']} for p in local]},
              open(os.path.join(ROOT, '.cursor-plugin', 'marketplace.json'), 'w'), indent=2)
    os.makedirs(os.path.join(ROOT, '.agents', 'plugins'), exist_ok=True)
    json.dump({'name': MARKETPLACE, 'interface': {'displayName': 'SFP'},
               'plugins': [{'name': p['name'], 'version': VERSION, 'source': {'source': 'local', 'path': p['source']},
                            'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'} for p in local]},
              open(os.path.join(ROOT, '.agents', 'plugins', 'marketplace.json'), 'w'), indent=2)
    # Gemini CLI: one extension that serves every skill through the MCP server in this repo.
    json.dump({'name': MARKETPLACE, 'version': VERSION,
               'description': 'SFP: %d agent skills, searchable and readable on demand, with a hive that picks the few each task needs.' % len(catalog),
               'mcpServers': {'sfp': {'command': 'python3', 'args': ['${extensionPath}/mcp/sfp_mcp.py']}}},
              open(os.path.join(ROOT, 'gemini-extension.json'), 'w'), indent=2)

    json.dump({'categories': meta, 'profiles': cfg['profiles'], 'skills': catalog},
              open(os.path.join(ROOT, 'catalog.json'), 'w'), indent=1)

    lines = ['# Skill catalog', '', 'Generated by `scripts/sync.py`. Do not edit by hand.', '']
    for cat, info in meta.items():
        rows = [c for c in catalog if c['category'] == cat]
        lines += [f"## {cat} ({info['skills'] or 'plugin'})", '', info['description'], '']
        if info.get('claude_only'):
            lines += ['Claude Code only: install it as a plugin from the marketplace.', '']
        if rows:
            lines += ['| Skill | What it does |', '|---|---|']
            for c in rows:
                d = c['description'].replace('|', '\\|')
                lines.append(f"| `{c['name']}` | {d[:200] + ('…' if len(d) > 200 else '')} |")
            lines.append('')
    open(os.path.join(ROOT, 'SKILLS.md'), 'w', encoding='utf-8').write('\n'.join(lines))


if __name__ == '__main__':
    main()
