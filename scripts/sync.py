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
IGNORE = shutil.ignore_patterns('.git', 'node_modules', '__pycache__', '.DS_Store', 'bin')
MARKETPLACE = 'sfp'
VERSION = '1.0.0'
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


def tree_hash(path):
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(path)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(d, f)
            if os.path.isfile(p):
                h.update(os.path.relpath(p, path).encode())
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
    if src_dir and os.path.isdir(os.path.join(src_dir, name)):
        return os.path.join(src_dir, name)
    dest = os.path.join(cache, name)
    if not os.path.isdir(dest):
        subprocess.run(['git', 'clone', '-q', '--depth', '1', f'https://github.com/{repo}.git', dest], check=True)
    return dest


def copy_skill(src, dest):
    shutil.copytree(src, dest, ignore=IGNORE, symlinks=False, ignore_dangling_symlinks=True)


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
        entry = {
            'name': name, 'category': cat,
            'description': ' '.join(field(fm, 'description').split()),
            'source': source['repo'], 'license': source.get('license', ''),
            'path': os.path.relpath(dest, ROOT), 'variants': {},
        }
        for tool, vsrc in (variants or {}).items():
            vdest = os.path.join(OUT, cat, 'variants', tool, name)
            copy_skill(vsrc, vdest)
            rename_skill(vdest, name)
            entry['variants'][tool] = os.path.relpath(vdest, ROOT)
        catalog.append(entry)
        licenses.setdefault(cat, set()).add(source['repo'])

    lic_by_repo = {}
    for source in cfg['sources']:
        if 'local' in source:
            repo_dir = os.path.join(ROOT, source['local'])
        else:
            repo_dir = checkout(source['repo'], args.src_dir, cache)
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
            add(staged, source, prefix)
        for pattern in source.get('skills', []):
            for skill_src in sorted(glob.glob(os.path.join(repo_dir, pattern))):
                rel = os.path.relpath(skill_src, repo_dir)
                if not os.path.isfile(os.path.join(skill_src, 'SKILL.md')):
                    continue
                if any(fnmatch.fnmatch(rel, e) for e in excludes):
                    continue
                variants = {t: os.path.join(repo_dir, p) for t, p in source.get('variants', {}).items()
                            if os.path.isfile(os.path.join(repo_dir, p, 'SKILL.md'))}
                add(skill_src, source, prefix, variants)
        lic = next((f for f in sorted(os.listdir(repo_dir)) if f.upper().startswith(('LICENSE', 'LICENCE'))), None)
        if lic:
            lic_by_repo[source['repo']] = os.path.join(repo_dir, lic)

    # Copy each category's source licenses next to its skills.
    for cat, repos in licenses.items():
        for repo in sorted(repos):
            if repo in lic_by_repo:
                d = os.path.join(OUT, cat, 'LICENSES')
                os.makedirs(d, exist_ok=True)
                shutil.copy(lic_by_repo[repo], os.path.join(d, repo.split('/')[1] + '.txt'))

    # The router skill: a template plus a generated index of every other skill.
    router = os.path.join(OUT, 'sfp', 'skills', 'sfp')
    os.makedirs(os.path.dirname(router), exist_ok=True)
    shutil.copytree(os.path.join(ROOT, 'templates', 'sfp'), router)
    os.makedirs(os.path.join(router, 'reference'), exist_ok=True)
    write_index(os.path.join(router, 'reference', 'index.md'), cats, cfg, catalog)
    catalog.append({
        'name': 'sfp', 'category': 'sfp',
        'description': ' '.join(field(frontmatter(open(os.path.join(router, 'SKILL.md'), encoding='utf-8').read()), 'description').split()),
        'source': 'siddu1004/SFP', 'license': '', 'path': os.path.relpath(router, ROOT), 'variants': {},
    })

    write_manifests(cfg, cats, catalog)
    update_docs(cfg, catalog)
    used = sorted({c['category'] for c in catalog})
    print(f'{len(catalog)} skills in {len(used)} categories')
    if args.report:
        for cat in used:
            names = [c['name'] for c in catalog if c['category'] == cat]
            print(f'\n{cat} ({len(names)}): ' + ', '.join(names))


def update_docs(cfg, catalog):
    """Rewrite the counts in README.md and assets/banner.svg from the catalog."""
    total = len(catalog)
    with_skills = len({c['category'] for c in catalog})
    repos = len({s['repo'] for s in cfg['sources']} | {e['app']['repo'] for e in cfg['externals'].values() if 'app' in e})
    per_cat = {}
    for c in catalog:
        per_cat[c['category']] = per_cat.get(c['category'], 0) + 1

    readme = os.path.join(ROOT, 'README.md')
    if os.path.isfile(readme):
        t = open(readme, encoding='utf-8').read()
        t = re.sub(r'skills-\d+-22c55e', f'skills-{total}-22c55e', t)
        t = re.sub(r'categories-\d+-8b5cf6', f'categories-{with_skills}-8b5cf6', t)
        t = re.sub(r'\d+ skills, \d+ categories, 16 IDEs', f'{total} skills, {with_skills} categories, 16 IDEs', t)
        t = re.sub(r'<b>\d+ agent skills from \d+ [a-z ]+, sorted', f'<b>{total} agent skills from {repos} sources, sorted', t)
        t = re.sub(r'alt="\d+ skills"', f'alt="{total} skills"', t)
        t = re.sub(r'(index of|and) \d+ (skills|descriptions)', lambda m: f'{m.group(1)} {total} {m.group(2)}', t)
        t = re.sub(r'install all \d+', f'install all {total}', t)
        t = re.sub(r'(\d+) categories: frontend', f'{with_skills} categories: frontend', t)
        for cat, n in per_cat.items():
            t = re.sub(rf'(\| `{re.escape(cat)}` \| )\d+( \|)', rf'\g<1>{n}\g<2>', t)
        open(readme, 'w', encoding='utf-8').write(t)
    banner = os.path.join(ROOT, 'assets', 'banner.svg')
    if os.path.isfile(banner):
        t = open(banner, encoding='utf-8').read()
        t = re.sub(r'\d+ skills</text>', f'{total} skills</text>', t)
        t = re.sub(r'\d+ categories</text>', f'{with_skills} categories</text>', t)
        t = re.sub(r'\d+ agent skills in \d+ categories', f'{total} agent skills in {with_skills} categories', t)
        open(banner, 'w', encoding='utf-8').write(t)


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
        json.dump({'name': cat, 'version': VERSION, 'description': desc, 'author': {'name': 'siddu1004'},
                   'repository': 'https://github.com/siddu1004/SFP', 'skills': './skills/'},
                  open(os.path.join(d, 'plugin.json'), 'w'), indent=2)
    for name, ext in cfg['externals'].items():
        plugins.append({'name': name, 'description': ext['description'], 'category': 'skills', 'source': ext['claude']})
        meta[name] = {k: v for k, v in ext.items() if k != 'claude'}
        meta[name]['skills'] = counts.get(name, 0)

    os.makedirs(os.path.join(ROOT, '.claude-plugin'), exist_ok=True)
    json.dump({
        '$schema': 'https://anthropic.com/claude-code/marketplace.schema.json',
        'name': MARKETPLACE,
        'owner': {'name': 'siddu1004'},
        'metadata': {'description': "SFP, Skills for Productivity: skills from many repos in one place, sorted by what you build, for Claude Code and every other agent IDE."},
        'plugins': plugins,
    }, open(os.path.join(ROOT, '.claude-plugin', 'marketplace.json'), 'w'), indent=2)

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
