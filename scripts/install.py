#!/usr/bin/env python3
"""Install SFP skills into any agent IDE or CLI.

  python3 scripts/install.py list
  python3 scripts/install.py install                              # starter profile, every tool found
  python3 scripts/install.py install --profile backend-dev
  python3 scripts/install.py install --categories frontend,security --tools cursor,codex
  python3 scripts/install.py install --profile everything         # all categories (heavy)
  python3 scripts/install.py install --project .                  # into this project's tool folders
  python3 scripts/install.py uninstall --tools cursor
  python3 scripts/install.py mcp --tools cursor,claude            # register the SFP MCP server
  python3 scripts/install.py rules --project .                    # standing instruction: use the hive on every substantial task
  python3 scripts/install.py apps list                            # programs some skills guide (OmniRoute, Strix...)
  python3 scripts/install.py apps install omniroute [--yes]       # plan first; --yes runs it

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
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser('~')
MARKER = '.sfp'
RENAMED = ('sfp-manager', 'sfp-select')   # skills this installer used to create under another name; removed on install
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


def app_data_base():
    if sys.platform == 'darwin':
        return h('Library', 'Application Support')
    if os.name == 'nt':
        return os.environ.get('APPDATA') or h('AppData', 'Roaming')
    return os.environ.get('XDG_CONFIG_HOME') or h('.config')


def app_user_dir(app_name):
    return os.path.join(app_data_base(), app_name, 'User')


def vscode_user_dir():
    """VS Code's per-user settings folder (it holds settings.json and mcp.json)."""
    return app_user_dir('Code')


# tool: (label, folders whose existence means the tool is installed, global skills dir, project config dir)
TOOLS = {
    'claude':      ('Claude Code',        [h('.claude'), app_user_dir('Claude')],         h('.claude', 'skills'),             '.claude'),
    'codex':       ('OpenAI Codex',       [h('.codex'), h('.agents')],                    h('.agents', 'skills'),             '.agents'),
    'cursor':      ('Cursor',             [h('.cursor'), app_user_dir('Cursor')],         h('.cursor', 'skills'),             '.cursor'),
    'gemini':      ('Gemini CLI',         [h('.gemini')],                                 h('.gemini', 'skills'),             '.gemini'),
    'antigravity': ('Google Antigravity', [h('.gemini', 'antigravity'), h('.gemini', 'antigravity-cli'),
                                           h('.gemini', 'antigravity-ide'), h('.gemini', 'config'),
                                           h('.antigravity'), h('.antigravity-ide'),
                                           app_user_dir('Antigravity'), app_user_dir('Antigravity IDE')],
                                                                                          h('.gemini', 'config', 'skills'),   '.agent'),
    'copilot':     ('GitHub Copilot and VS Code', [h('.copilot'), vscode_user_dir(), app_user_dir('Code - Insiders'),
                                                   app_user_dir('VSCodium'), h('.vscode'), h('.vscode-insiders')],
                                                                                          h('.copilot', 'skills'),            '.github'),
    'windsurf':    ('Windsurf',           [h('.codeium', 'windsurf'), h('.windsurf'),
                                           app_user_dir('Windsurf'), app_user_dir('Windsurf - Next')],
                                                                                          h('.codeium', 'windsurf', 'skills'), '.windsurf'),
    'kiro':        ('Kiro',               [h('.kiro'), app_user_dir('Kiro')],             h('.kiro', 'skills'),               '.kiro'),
    'opencode':    ('OpenCode',           [opencode_dir(), h('.opencode')],               os.path.join(opencode_dir(), 'skills'), '.opencode'),
    'pi':          ('Pi',                 [h('.pi')],                                     h('.pi', 'agent', 'skills'),        '.pi'),
    'grok':        ('Grok Build',         [h('.grok')],                                   h('.grok', 'skills'),               '.grok'),
    'qoder':       ('Qoder',              [h('.qoder'), app_user_dir('Qoder')],           h('.qoder', 'skills'),              '.qoder'),
    'trae':        ('Trae',               [h('.trae'), h('.trae-cn'), app_user_dir('Trae')], h('.trae', 'skills'),            '.trae'),
    'rovodev':     ('Rovo Dev',           [h('.rovodev')],                                h('.rovodev', 'skills'),            '.rovodev'),
    'vibe':        ('Mistral Vibe',       [h('.vibe')],                                   h('.vibe', 'skills'),               '.vibe'),
    'hermes':      ('Hermes',             [h('.hermes')],                                 h('.hermes', 'skills'),             '.hermes'),
    'cline':       ('Cline',              [h('.cline')],                                  h('.cline', 'skills'),              '.cline'),
    'roo':         ('Roo Code',           [h('.roo'), h('.roocode')],                     h('.roo', 'skills'),                '.roo'),
    'zed':         ('Zed',                [h('.config', 'zed'), h('.zed'), os.path.join(app_data_base(), 'Zed')],
                                                                                          h('.config', 'zed', 'skills'),      '.zed'),
    'continue':    ('Continue',           [h('.continue')],                               h('.continue', 'skills'),           '.continue'),
    'aider':       ('Aider',              [h('.aider')],                                  h('.aider', 'skills'),              '.aider'),
    'goose':       ('Goose',              [h('.config', 'goose'), h('.goose')],           h('.config', 'goose', 'skills'),    '.goose'),
    'amp':         ('Amp',                [h('.config', 'amp'), h('.amp')],               h('.config', 'amp', 'skills'),      '.amp'),
    'augment':     ('Augment Code',       [h('.augment')],                                h('.augment', 'skills'),            '.augment'),
    'crush':       ('Crush',              [h('.config', 'crush'), h('.crush')],           h('.config', 'crush', 'skills'),    '.crush'),
    'pearai':      ('PearAI',             [h('.pearai'), app_user_dir('PearAI')],         h('.pearai', 'skills'),             '.pearai'),
    'void':        ('Void',               [h('.void'), app_user_dir('Void')],             h('.void', 'skills'),               '.void'),
    'positron':    ('Positron',           [h('.positron'), app_user_dir('Positron')],     h('.positron', 'skills'),           '.positron'),
}

TOOL_ALIASES = {
    'vscode': 'copilot',
    'vscode-insiders': 'copilot',
    'code': 'copilot',
    'code-insiders': 'copilot',
    'codium': 'copilot',
    'vscodium': 'copilot',
    'antigravity-ide': 'antigravity',
    'antigravity-cli': 'antigravity',
    'agy': 'antigravity',
    'claude-code': 'claude',
    'claude-desktop': 'claude',
    'gemini-cli': 'gemini',
    'cursor-nightly': 'cursor',
    'windsurf-next': 'windsurf',
    'trae-cn': 'trae',
    'roocode': 'roo',
    'roo-code': 'roo',
    'augment-code': 'augment',
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
    if value == 'all':
        return list(TOOLS)
    picked = [TOOL_ALIASES.get(t, t) for t in split(value)]  # VS Code and IDE aliases map to canonical tool keys
    return check(list(dict.fromkeys(picked)), TOOLS, 'tool')


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


def extra_skills_dirs(tool, project):
    """Additional version-specific skill directories for tools that changed paths across versions."""
    extra = []
    if tool == 'antigravity':
        if project:
            agents_dir = os.path.join(os.path.abspath(project), '.agents')
            if os.path.isdir(agents_dir):
                extra.append(os.path.join(agents_dir, 'skills'))
        else:
            for sub in ('antigravity', 'antigravity-ide', 'antigravity-cli'):
                d = h('.gemini', sub, 'skills')
                if os.path.isdir(d):
                    extra.append(d)
    return extra


def owned(path):
    if os.path.islink(path):
        target = os.path.realpath(path)
        return target.startswith(ROOT + os.sep) or os.sep + '.sfp' + os.sep in target
    return os.path.isfile(os.path.join(path, MARKER))


def touch_skill(dest, ts=None):
    skill_md = os.path.join(dest, 'SKILL.md')
    try:
        if os.path.isfile(skill_md):
            os.utime(skill_md, (ts, ts) if ts is not None else None)
        if os.path.isdir(dest) and not os.path.islink(dest):
            os.utime(dest, (ts, ts) if ts is not None else None)
    except OSError:
        pass


def prioritize_core_skills(dest_root):
    """Ensure sfp and sfp-hive always have the newest mtime so context-budget limits never evict them."""
    now = time.time() + 1.0
    for idx, core in enumerate(('sfp-hive', 'sfp')):
        p = os.path.join(dest_root, core)
        if os.path.exists(p):
            touch_skill(p, now + idx)


def install_antigravity_plugin(force, link):
    """Install the sfp plugin into ~/.gemini/config/plugins/sfp and enable it in config.json when present."""
    cfg_dir = h('.gemini', 'config')
    src = os.path.join(ROOT, 'plugins', 'sfp')
    if not (os.path.isdir(cfg_dir) and os.path.isdir(src)):
        return
    plugins_dir = os.path.join(cfg_dir, 'plugins')
    os.makedirs(plugins_dir, exist_ok=True)
    dest = os.path.join(plugins_dir, 'sfp')
    place(src, dest, 'sfp', force, link)
    for skill_name in ('sfp', 'sfp-hive'):
        touch_skill(os.path.join(dest, 'skills', skill_name))
    cfg_path = os.path.join(cfg_dir, 'config.json')
    cfg = {}
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding='utf-8') as f:
                cfg = json.load(f)
        except ValueError:
            return
    if not isinstance(cfg, dict):
        return
    plugins = cfg.setdefault('plugins', {})
    if isinstance(plugins, dict) and plugins.get('sfp') != {'enabled': True}:
        plugins['sfp'] = {'enabled': True}
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
            f.write('\n')


def uninstall_antigravity_plugin():
    cfg_dir = h('.gemini', 'config')
    dest = os.path.join(cfg_dir, 'plugins', 'sfp')
    if os.path.lexists(dest) and owned(dest):
        if os.path.islink(dest) or os.path.isfile(dest):
            os.remove(dest)
        else:
            shutil.rmtree(dest)
    cfg_path = os.path.join(cfg_dir, 'config.json')
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding='utf-8') as f:
                cfg = json.load(f)
            if isinstance(cfg, dict) and isinstance(cfg.get('plugins'), dict) and 'sfp' in cfg['plugins']:
                cfg['plugins'].pop('sfp', None)
                with open(cfg_path, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, indent=2)
                    f.write('\n')
        except ValueError:
            pass


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
        touch_skill(dest)
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


def install_into_dir(dest_root, tool, names, cat, apps, apps_dir, args):
    os.makedirs(dest_root, exist_ok=True)
    print(f'  {TOOLS[tool][0]}: {dest_root}')
    for old in RENAMED:   # a skill renamed since the last install: remove the old copy, but only if SFP made it
        stale = os.path.join(dest_root, old)
        if os.path.lexists(stale) and owned(stale):
            if os.path.islink(stale) or os.path.isfile(stale):
                os.remove(stale)
            else:
                shutil.rmtree(stale)
            print(f'    removed {old} (renamed to sfp-hive)')
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
    prioritize_core_skills(dest_root)
    print(f'    {count} skills installed')
    if count > WARN_AT:
        print(f'    note: {count} skills is a lot for one agent. Agents read every skill description up front; '
              f'the sfp skill can reach the rest on demand, so consider fewer categories.')


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
        targets = [skills_dir(tool, args.project)] + extra_skills_dirs(tool, args.project)
        for dest_root in dict.fromkeys(targets):
            install_into_dir(dest_root, tool, names, cat, apps, apps_dir, args)
        if tool == 'antigravity' and not args.project:
            install_antigravity_plugin(args.force, args.link)
    for name, got in apps.items():
        if got is None:
            continue
        setup = cat['categories'][name]['app'].get('setup')
        print(f'  {name} lives in {got[1]}.' + (f' Set it up once there: {setup}.' if setup else ''))
    print(f'\n  SFP checkout recorded in {os.path.join(HOME, ".sfp", "root")}: the `sfp` skill can read any skill from there on demand.')


def cmd_uninstall(args):
    for tool in pick_tools(args.tools):
        targets = [skills_dir(tool, args.project)] + extra_skills_dirs(tool, args.project)
        for root in dict.fromkeys(targets):
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
        if tool == 'antigravity' and not args.project:
            uninstall_antigravity_plugin()
        if tool == 'claude' and not args.project and shutil.which('claude'):
            print(f'  Claude Code plugins stay installed. Remove them with: claude plugin uninstall <category>@{MARKETPLACE}')


# MCP: tools whose MCP settings live in one JSON file with an "mcpServers" object.
MCP_JSON = {
    'antigravity': h('.gemini', 'config', 'mcp_config.json'),
    'cursor':      h('.cursor', 'mcp.json'),
    'gemini':      h('.gemini', 'settings.json'),
    'windsurf':    h('.codeium', 'windsurf', 'mcp_config.json'),
    'kiro':        h('.kiro', 'settings', 'mcp.json'),
    'opencode':    os.path.join(opencode_dir(), 'mcp.json'),
    'trae':        h('.trae', 'mcp.json'),
    'qoder':       h('.qoder', 'mcp.json'),
    'rovodev':     h('.rovodev', 'mcp.json'),
    'vibe':        h('.vibe', 'mcp.json'),
    'hermes':      h('.hermes', 'mcp.json'),
    'grok':        h('.grok', 'mcp.json'),
    'pi':          h('.pi', 'mcp.json'),
    'cline':       h('.cline', 'mcp_settings.json'),
    'roo':         h('.roo', 'mcp_settings.json'),
    'continue':    h('.continue', 'config.json'),
    'zed':         h('.config', 'zed', 'settings.json'),
    'goose':       h('.config', 'goose', 'mcp.json'),
    'amp':         h('.config', 'amp', 'settings.json'),
    'augment':     h('.augment', 'mcp.json'),
    'crush':       h('.config', 'crush', 'mcp.json'),
    'pearai':      h('.pearai', 'mcp.json'),
    'void':        h('.void', 'mcp.json'),
    'positron':    h('.positron', 'mcp.json'),
}
MCP_SERVER = os.path.join(ROOT, 'mcp', 'sfp_mcp.py')


def mcp_entry():
    return {'command': sys.executable, 'args': [MCP_SERVER]}


def mcp_snippet(tool):
    entry = json.dumps({'mcpServers': {'sfp': mcp_entry()}}, indent=2)
    if tool == 'codex':
        return f'[mcp_servers.sfp]\ncommand = {json.dumps(sys.executable)}\nargs = [{json.dumps(MCP_SERVER)}]'
    return entry


def update_mcp_json_file(label, tool, path, remove, key='mcpServers', extra_fields=None):
    cfg = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding='utf-8') as f:
                cfg = json.load(f)
        except ValueError:
            print(f'  {label}: {path} is not valid JSON, so I left it alone. Add this by hand:\n{mcp_snippet(tool)}')
            return False
        shutil.copy(path, path + '.sfp-backup')
    servers = cfg.setdefault(key, {})
    if remove:
        servers.pop('sfp', None)
    else:
        entry = dict(mcp_entry())
        if extra_fields:
            entry.update(extra_fields)
        servers['sfp'] = entry
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
        f.write('\n')
    print(f'  {label}: {"removed from" if remove else "added to"} {path}')
    return True


def mcp_json_targets(tool, project):
    if project:
        proj_root = os.path.abspath(project)
        if tool == 'antigravity':
            targets = [os.path.join(proj_root, '.agent', 'mcp_config.json')]
            if os.path.isdir(os.path.join(proj_root, '.agents')):
                targets.append(os.path.join(proj_root, '.agents', 'mcp_config.json'))
            return targets
        return [os.path.join(proj_root, TOOLS[tool][3], 'mcp.json')]
    targets = [MCP_JSON[tool]]
    if tool == 'antigravity':
        for sub in ('antigravity', 'antigravity-ide', 'antigravity-cli'):
            legacy_dir = h('.gemini', sub)
            legacy_file = os.path.join(legacy_dir, 'mcp_config.json')
            if os.path.isdir(legacy_dir) or os.path.isfile(legacy_file):
                targets.append(legacy_file)
    return list(dict.fromkeys(targets))


def cmd_mcp(args):
    """Register the SFP MCP server in each IDE's MCP settings (or print what to add)."""
    tools = pick_tools(args.tools)
    if not tools:
        sys.exit('No supported tool found. Name one with --tools.')
    record_root()
    for tool in tools:
        label = TOOLS[tool][0]
        if tool == 'claude':
            if args.project:
                update_mcp_json_file(label, tool, os.path.join(os.path.abspath(args.project), '.mcp.json'), args.remove)
                continue
            if shutil.which('claude'):
                if args.remove:
                    subprocess.run(['claude', 'mcp', 'remove', '--scope', 'user', 'sfp'], check=False)
                else:
                    subprocess.run(['claude', 'mcp', 'add', '--scope', 'user', 'sfp', '--', sys.executable, MCP_SERVER], check=False)
            else:
                update_mcp_json_file(label, tool, h('.claude.json'), args.remove)
        elif tool == 'copilot':
            path = os.path.join(os.path.abspath(args.project), '.vscode', 'mcp.json') if args.project else os.path.join(vscode_user_dir(), 'mcp.json')
            cfg = {}
            if os.path.isfile(path):
                try:
                    with open(path, encoding='utf-8') as f:
                        cfg = json.load(f)
                except ValueError:   # VS Code allows comments in mcp.json; leave a file we cannot parse alone
                    print(f'  {label}: {path} has comments or is not plain JSON, so I left it alone. Add this under "servers":\n'
                          + json.dumps({'sfp': dict(mcp_entry(), type='stdio')}, indent=2))
                    continue
                shutil.copy(path, path + '.sfp-backup')
            servers = cfg.setdefault('servers', {})   # VS Code's key is "servers", not "mcpServers"
            if args.remove:
                servers.pop('sfp', None)
            else:
                servers['sfp'] = dict(mcp_entry(), type='stdio')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
                f.write('\n')
            print(f'  {label}: {"removed from" if args.remove else "added to"} {path}')
        elif tool in MCP_JSON:
            for path in mcp_json_targets(tool, args.project):
                update_mcp_json_file(label, tool, path, args.remove)
        elif tool == 'codex':
            path = os.path.join(os.path.abspath(args.project), '.codex', 'config.toml') if args.project else h('.codex', 'config.toml')
            text = open(path, encoding='utf-8').read() if os.path.isfile(path) else ''
            if args.remove:
                print(f'  {label}: delete the [mcp_servers.sfp] block from {path}')
            elif '[mcp_servers.sfp]' in text:
                print(f'  {label}: already in {path}')
            else:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if text:
                    shutil.copy(path, path + '.sfp-backup')
                with open(path, 'a', encoding='utf-8') as f:
                    f.write(('\n' if text and not text.endswith('\n') else '') + '\n' + mcp_snippet('codex') + '\n')
                print(f'  {label}: added to {path}')
        else:
            print(f'  {label}: add this to its MCP settings (stdio server named sfp):\n{mcp_snippet(tool)}')
    if not args.remove:
        print('\n  Restart the IDE, then ask it to use the sfp tools (search_skills, get_skill, find_api).')


RULES_START, RULES_END = '<!-- sfp:start -->', '<!-- sfp:end -->'
RULES_TEXT = RULES_START + '''
## SFP skills

At the start of a substantial task (build, fix, test, review, secure, deploy), use the `sfp-hive` skill, or the SFP MCP tool `select_skills` if it is connected, to pick the few skills that fit the task and this project. Read only those skills and follow them in the order given. When the task ends, report how each one went with `give_feedback` (helped, unhelpful, ignored, missing). For a single question, use the `sfp` skill to find one skill.
''' + RULES_END + '\n'

# Where each tool reads standing instructions: (user-level file, project file).
RULES_FILES = {
    'claude':      (h('.claude', 'CLAUDE.md'), 'CLAUDE.md'),
    'codex':       (h('.codex', 'AGENTS.md'), 'AGENTS.md'),
    'gemini':      (h('.gemini', 'GEMINI.md'), 'GEMINI.md'),
    'antigravity': (h('.gemini', 'GEMINI.md'), 'AGENTS.md'),
    'cursor':      (h('.cursor', 'rules', 'sfp.mdc'), 'AGENTS.md'),
    'copilot':     (h('.copilot', 'copilot-instructions.md'), 'AGENTS.md'),
    'windsurf':    (h('.codeium', 'windsurf', 'memories', 'global_rules.md'), 'AGENTS.md'),
    'kiro':        (h('.kiro', 'steering', 'sfp.md'), 'AGENTS.md'),
    'opencode':    (os.path.join(opencode_dir(), 'AGENTS.md'), 'AGENTS.md'),
    'trae':        (h('.trae', 'user_rules.md'), 'AGENTS.md'),
    'qoder':       (h('.qoder', 'AGENTS.md'), 'AGENTS.md'),
    'cline':       (h('.cline', 'AGENTS.md'), 'AGENTS.md'),
    'roo':         (h('.roo', 'rules', 'sfp.md'), 'AGENTS.md'),
    'zed':         (h('.config', 'zed', 'AGENTS.md'), 'AGENTS.md'),
    'continue':    (h('.continue', 'rules', 'sfp.md'), 'AGENTS.md'),
    'aider':       (h('.aider.conf.md'), 'AGENTS.md'),
    'goose':       (h('.config', 'goose', '.goosehints'), 'AGENTS.md'),
    'amp':         (h('.config', 'amp', 'AGENTS.md'), 'AGENTS.md'),
    'augment':     (h('.augment', 'rules.md'), 'AGENTS.md'),
    'crush':       (h('.config', 'crush', 'AGENTS.md'), 'AGENTS.md'),
    'pearai':      (h('.pearai', 'AGENTS.md'), 'AGENTS.md'),
    'void':        (h('.void', 'AGENTS.md'), 'AGENTS.md'),
    'positron':    (h('.positron', 'AGENTS.md'), 'AGENTS.md'),
    'pi':          (h('.pi', 'agent', 'AGENTS.md'), 'AGENTS.md'),
    'grok':        (h('.grok', 'AGENTS.md'), 'AGENTS.md'),
    'rovodev':     (h('.rovodev', 'AGENTS.md'), 'AGENTS.md'),
    'vibe':        (h('.vibe', 'AGENTS.md'), 'AGENTS.md'),
    'hermes':      (h('.hermes', 'AGENTS.md'), 'AGENTS.md'),
}


def rules_files(tools, project):
    """The instruction files to put the block in. Tools with no file of their own share AGENTS.md in a project."""
    files = []
    for tool in tools:
        user, proj = RULES_FILES.get(tool, (None, 'AGENTS.md'))
        path = os.path.join(os.path.abspath(project), proj) if project else user
        if path is None:
            print(f'  {TOOLS[tool][0]}: no user-level instructions file. Run again with --project <folder>.')
        elif path not in files:
            files.append(path)
    return files


def with_rules(text, remove):
    """text with the SFP block replaced, added at the end, or (remove) taken out. The rest is untouched."""
    a = text.find(RULES_START)
    b = text.find(RULES_END, a) if a >= 0 else -1
    if a < 0 or b < 0:
        if remove:
            return text
        return text.rstrip('\n') + ('\n\n' if text.strip() else '') + RULES_TEXT
    end = b + len(RULES_END)
    if text[end:end + 1] == '\n':
        end += 1
    before, after = text[:a].rstrip('\n'), text[end:].lstrip('\n')
    if remove:
        return before + ('\n\n' if before and after else ('\n' if before else '')) + after
    return before + ('\n\n' if before else '') + RULES_TEXT + ('\n' + after if after else '')


def cmd_rules(args):
    """Add (or --remove) a short standing instruction so the agent uses the hive without being told each time."""
    tools = pick_tools(args.tools)
    if not tools:
        sys.exit('No supported tool found. Name one with --tools.')
    for path in rules_files(tools, args.project):
        text = open(path, encoding='utf-8').read() if os.path.isfile(path) else ''
        new = with_rules(text, args.remove)
        if new == text:
            print(f'  {path}: nothing to change')
            continue
        if text:
            shutil.copy(path, path + '.sfp-backup')
        if not new.strip():
            os.remove(path)   # the file held only our block
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new)
        print(f'  {path}: {"removed the SFP block" if args.remove else "SFP block written"}')


def cmd_apps(rest):
    """`install.py apps status|install|update|start|list [ID] [--yes]`: set up the programs some skills guide."""
    sys.path.insert(0, os.path.join(ROOT, 'apps'))
    import sfp_app
    os.environ.setdefault('SFP_APPS_FILE', os.path.join(ROOT, 'apps', 'apps.json'))
    sys.exit(sfp_app.main(rest))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'apps':
        cmd_apps(sys.argv[2:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['list', 'install', 'uninstall', 'mcp', 'rules'])
    ap.add_argument('--remove', action='store_true', help='with `mcp` or `rules`: remove what was added')
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
    elif args.command == 'mcp':
        cmd_mcp(args)
    elif args.command == 'rules':
        cmd_rules(args)
    else:
        cmd_uninstall(args)


if __name__ == '__main__':
    main()
