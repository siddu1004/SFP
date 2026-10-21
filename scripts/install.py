#!/usr/bin/env python3
"""Install SFP skills into any agent IDE or CLI.

  python3 scripts/install.py list
  python3 scripts/install.py install                              # starter profile, every tool found
  python3 scripts/install.py install --profile backend-dev
  python3 scripts/install.py install --categories frontend,security --tools cursor,codex
  python3 scripts/install.py install --profile everything         # all categories (heavy)
  python3 scripts/install.py install --project .                  # into this project's tool folders
  python3 scripts/install.py uninstall --tools cursor

Every install also adds the `sfp` router skill and records this checkout in
~/.sfp/root, so an agent can read any SFP skill on demand without installing it.
Only folders this script created (they hold a .sfp marker) are replaced or removed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser('~')
MARKER = '.sfp'
MARKETPLACE = 'sfp'
WARN_AT = 150


def opencode_dir():
    if os.environ.get('OPENCODE_CONFIG_DIR'):
        return os.environ['OPENCODE_CONFIG_DIR']
    if os.environ.get('XDG_CONFIG_HOME'):
        return os.path.join(os.environ['XDG_CONFIG_HOME'], 'opencode')
    return os.path.join(HOME, '.config', 'opencode')


def h(*parts):
    return os.path.join(HOME, *parts)


# tool: (label, folders whose existence means the tool is installed, global skills dir, project config dir)
TOOLS = {
    'claude':      ('Claude Code',        [h('.claude')],                                 h('.claude', 'skills'),             '.claude'),
    'codex':       ('OpenAI Codex',       [h('.codex'), h('.agents')],                    h('.agents', 'skills'),             '.agents'),
    'cursor':      ('Cursor',             [h('.cursor')],                                 h('.cursor', 'skills'),             '.cursor'),
    'gemini':      ('Gemini CLI',         [h('.gemini')],                                 h('.gemini', 'skills'),             '.gemini'),
    'antigravity': ('Google Antigravity', [h('.gemini', 'antigravity'), h('.gemini', 'antigravity-cli'),
                                           h('.gemini', 'antigravity-ide')],              h('.gemini', 'config', 'skills'),   '.agent'),
    'copilot':     ('GitHub Copilot',     [h('.copilot')],                                h('.copilot', 'skills'),            '.github'),
    'windsurf':    ('Windsurf',           [h('.codeium', 'windsurf')],                    h('.codeium', 'windsurf', 'skills'), '.windsurf'),
    'kiro':        ('Kiro',               [h('.kiro')],                                   h('.kiro', 'skills'),               '.kiro'),
    'opencode':    ('OpenCode',           [opencode_dir(), h('.opencode')],               os.path.join(opencode_dir(), 'skills'), '.opencode'),
    'pi':          ('Pi',                 [h('.pi')],                                     h('.pi', 'agent', 'skills'),        '.pi'),
    'grok':        ('Grok Build',         [h('.grok')],                                   h('.grok', 'skills'),               '.grok'),
    'qoder':       ('Qoder',              [h('.qoder')],                                  h('.qoder', 'skills'),              '.qoder'),
    'trae':        ('Trae',               [h('.trae')],                                   h('.trae', 'skills'),               '.trae'),
    'rovodev':     ('Rovo Dev',           [h('.rovodev')],                                h('.rovodev', 'skills'),            '.rovodev'),
    'vibe':        ('Mistral Vibe',       [h('.vibe')],                                   h('.vibe', 'skills'),               '.vibe'),
    'hermes':      ('Hermes',             [h('.hermes')],                                 h('.hermes', 'skills'),             '.hermes'),
}


def load_catalog():
    with open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8') as f:
        return json.load(f)


def detected_tools():
    return [t for t, (_, marks, _, _) in TOOLS.items() if any(os.path.isdir(m) for m in marks)]


def split(value):
    return [v.strip() for v in value.split(',') if v.strip()]


def check(picked, choices, what):
    unknown = [v for v in picked if v not in choices]
    if unknown:
        sys.exit(f"Unknown {what}: {', '.join(unknown)}. Choose from: {', '.join(choices)}")
    return picked


def pick_tools(value):
    if value in (None, '', 'auto'):
        return detected_tools()
    return list(TOOLS) if value == 'all' else check(split(value), TOOLS, 'tool')


def pick_categories(cat, args):
    names = list(cat['categories'])
    if args.categories:
        picked = names if args.categories == 'all' else check(split(args.categories), names, 'category')
    else:
        profile = args.profile or 'starter'
        if profile == 'everything':
            picked = [n for n in names if not cat['categories'][n].get('optional')]
        elif profile in cat['profiles']:
            picked = list(cat['profiles'][profile])
        else:
            sys.exit(f"Unknown profile: {profile}. Choose from: {', '.join(list(cat['profiles']) + ['everything'])}")
    if 'sfp' not in picked:
        picked = ['sfp'] + picked
    return picked


def skills_dir(tool, project):
    if project:
        return os.path.join(os.path.abspath(project), TOOLS[tool][3], 'skills')
    return TOOLS[tool][2]


def owned(path):
    if os.path.islink(path):
        target = os.path.realpath(path)
        return target.startswith(ROOT + os.sep) or os.sep + '.sfp' + os.sep in target
    return os.path.isfile(os.path.join(path, MARKER))


def place(src, dest, label, force, link):
    if os.path.lexists(dest):
        if not (owned(dest) or force):
            print(f'    skip {os.path.basename(dest)}: a skill with that name is already there (use --force to replace)')
            return False
        if os.path.islink(dest) or os.path.isfile(dest):
            os.remove(dest)
        else:
            shutil.rmtree(dest)
    if link:
        os.symlink(src, dest, target_is_directory=True)
    else:
        shutil.copytree(src, dest)
        with open(os.path.join(dest, MARKER), 'w') as f:
            f.write(label + '\n')
    return True


def install_app(spec, apps_dir):
    """Clone a skill that runs from its own checkout and return a pointer skill for it."""
    checkout = os.path.join(apps_dir, spec['name'])
    if os.path.isdir(os.path.join(checkout, '.git')):
        subprocess.run(['git', '-C', checkout, 'pull', '-q', '--ff-only'], check=False)
    else:
        os.makedirs(apps_dir, exist_ok=True)
        cmd = ['git', 'clone', '-q', '--depth', '1']
        if spec.get('ref'):
            cmd += ['--branch', spec['ref']]
        done = subprocess.run(cmd + [f"https://github.com/{spec['repo']}.git", checkout])
        if done.returncode != 0:
            return None
    skill = os.path.join(checkout, spec['skill'], 'SKILL.md')
    with open(skill, encoding='utf-8') as f:
        text = f.read()
    end = text.find('\n---', 3)
    head = text[:end] if text.startswith('---') and end > 0 else f"---\nname: {spec['name']}"
    pointer = os.path.join(apps_dir, '.pointers', spec['name'])
    os.makedirs(pointer, exist_ok=True)
    with open(os.path.join(pointer, 'SKILL.md'), 'w', encoding='utf-8') as f:
        f.write(f"{head}\n---\n\n"
                f"This skill runs from its own checkout at `{checkout}`.\n\n"
                f"Read `{skill}` and follow it. "
                f"Its project root is `{checkout}`: resolve every path it names against that folder, not this one.\n")
    return pointer, checkout


def claude_plugins(names):
    if not shutil.which('claude'):
        return False
    print('  Claude Code: installing categories as plugins')
    subprocess.run(['claude', 'plugin', 'marketplace', 'add', ROOT], check=False)
    for n in names:
        subprocess.run(['claude', 'plugin', 'install', f'{n}@{MARKETPLACE}'], check=False)
    return True


def record_root():
    d = os.path.join(HOME, '.sfp')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'root'), 'w') as f:
        f.write(ROOT + '\n')


def cmd_list(cat):
    print('Categories:')
    for name, b in cat['categories'].items():
        extra = ' (Claude Code only)' if b.get('claude_only') else ''
        extra += ' (optional)' if b.get('optional') else ''
        count = f"{b['skills']:4} skills" if b['skills'] else '  1 plugin'
        print(f'  {name:17} {count}{extra}')
        print(f"                    {b['description']}")
    print('\nProfiles:')
    for name, cats in cat['profiles'].items():
        print(f"  {name:14} {', '.join(cats)}")
    print('  everything     all categories')
    found = detected_tools()
    print('\nTools found on this machine:', ', '.join(found) if found else 'none')
    print('All supported tools:', ', '.join(TOOLS))


def cmd_install(cat, args):
    tools = pick_tools(args.tools)
    names = pick_categories(cat, args)
    if not tools:
        sys.exit('No supported tool found. Name one with --tools (see `list`).')
    apps_dir = os.path.abspath(os.path.expanduser(args.apps_dir))
    apps = {}
    record_root()
    for tool in tools:
        if tool == 'claude' and not args.project and not args.copy and claude_plugins(names):
            continue
        dest_root = skills_dir(tool, args.project)
        os.makedirs(dest_root, exist_ok=True)
        print(f'  {TOOLS[tool][0]}: {dest_root}')
        count = 0
        for name in names:
            spec = cat['categories'][name]
            if spec.get('claude_only'):
                print(f'    skip {name}: Claude Code plugin only (install it with /plugin)')
                continue
            if spec.get('app'):
                if name not in apps:
                    apps[name] = install_app(spec['app'], apps_dir)
                if apps[name] is None:
                    print(f"    skip {name}: could not clone github.com/{spec['app']['repo']} "
                          f"(private repo, or no access with your git credentials)")
                    continue
                count += place(apps[name][0], os.path.join(dest_root, spec['app']['name']), name, args.force, args.link)
                continue
            for s in cat['skills']:
                if s['category'] != name:
                    continue
                rel = s['path'] if tool == 'claude' else s['variants'].get(tool, s['variants'].get('generic', s['path']))
                count += place(os.path.join(ROOT, rel), os.path.join(dest_root, s['name']), name, args.force, args.link)
        print(f'    {count} skills installed')
        if count > WARN_AT:
            print(f'    note: {count} skills is a lot for one agent. Agents read every skill description up front; '
                  f'the sfp skill can reach the rest on demand, so consider fewer categories.')
    for name, got in apps.items():
        if got is None:
            continue
        setup = cat['categories'][name]['app'].get('setup')
        print(f'  {name} lives in {got[1]}.' + (f' Set it up once there: {setup}.' if setup else ''))
    print(f'\n  SFP checkout recorded in {os.path.join(HOME, ".sfp", "root")}: the `sfp` skill can read any skill from there on demand.')


def cmd_uninstall(args):
    for tool in pick_tools(args.tools):
        root = skills_dir(tool, args.project)
        if not os.path.isdir(root):
            continue
        removed = 0
        for name in os.listdir(root):
            p = os.path.join(root, name)
            if os.path.islink(p) and owned(p):
                os.remove(p)
                removed += 1
            elif os.path.isdir(p) and not os.path.islink(p) and owned(p):
                shutil.rmtree(p)
                removed += 1
        print(f'  {TOOLS[tool][0]}: removed {removed} skills from {root}')
        if tool == 'claude' and not args.project and shutil.which('claude'):
            print(f'  Claude Code plugins stay installed. Remove them with: claude plugin uninstall <category>@{MARKETPLACE}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['list', 'install', 'uninstall'])
    ap.add_argument('--tools', help='comma-separated tools, "all", or "auto" (default: tools found on this machine)')
    ap.add_argument('--categories', help='comma-separated categories or "all"')
    ap.add_argument('--profile', help='starter (default), frontend-dev, backend-dev, mobile-dev, agent-builder, everything')
    ap.add_argument('--project', metavar='DIR', help="install into DIR's tool folders instead of your home folder")
    ap.add_argument('--apps-dir', default='~/.sfp/apps', help='where skills that need their own checkout are cloned')
    ap.add_argument('--copy', action='store_true', help='Claude Code: copy files instead of installing plugins')
    ap.add_argument('--link', action='store_true', help='symlink instead of copy, so `git pull` updates skills in place')
    ap.add_argument('--force', action='store_true', help='replace skills with the same name that this script did not install')
    args = ap.parse_args()
    cat = load_catalog()
    if args.command == 'list':
        cmd_list(cat)
    elif args.command == 'install':
        cmd_install(cat, args)
    else:
        cmd_uninstall(args)


if __name__ == '__main__':
    main()
