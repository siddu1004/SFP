#!/usr/bin/env python3
"""Check, install, start and update the program a skill needs. Standard library only.

Some skills are only a guide to a program that is installed separately (a gateway, a scanner, a
memory service). Each of those skills carries this file and the entry for its program, so the
agent can set the program up from inside the skill.

  python3 sfp_app.py status [ID]        what is installed, what is running, what is missing
  python3 sfp_app.py install [ID]       show the plan (changes nothing)
  python3 sfp_app.py install [ID] --yes run the plan
  python3 sfp_app.py update [ID] [--yes]
  python3 sfp_app.py start [ID]         start it and wait until it answers
  python3 sfp_app.py list               every program this file knows

ID is only needed when the file knows more than one program. Nothing is installed without --yes,
and a downloaded installer script is saved, hashed and shown before it runs.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWS = os.name == 'nt'


def load(path=None):
    path = path or os.environ.get('SFP_APPS_FILE') or os.path.join(HERE, 'app.json')
    if not os.path.isfile(path):
        path = os.path.join(HERE, 'apps.json')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    # One program per skill is stored as the entry itself; the router carries the whole table.
    return data if 'name' not in data else {data.get('id', 'app'): data}


def run(cmd, timeout=20):
    """Run a command quietly: (exit code, output), or (None, reason) when it cannot start."""
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)
    return done.returncode, (done.stdout or done.stderr or '').strip()


def version_of(tool):
    code, out = run([tool, '--version'])
    m = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', out or '')
    if code != 0 or not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def in_range(v, ranges):
    """ranges is [lo1, hi1, lo2, hi2, ...] as version triples, each pair a half-open [lo, hi)."""
    return any(tuple(ranges[i]) <= v < tuple(ranges[i + 1]) for i in range(0, len(ranges), 2))


def check_needs(app):
    """A list of (ok, message) for each thing the program needs before it can be installed."""
    results = []
    for need in app.get('needs', []):
        tool = need['tool']
        label = need.get('label', tool)
        if not shutil.which(tool):
            results.append((False, '%s is not installed%s' % (label, (': ' + need['url']) if need.get('url') else '')))
            continue
        if need.get('range'):
            v = version_of(tool)
            if v is None or not in_range(v, need['range']):
                found = '.'.join(map(str, v)) if v else 'unknown'
                results.append((bool(need.get('soft')), '%s needed, found %s %s%s' % (label, tool, found, (': ' + need['url']) if need.get('url') else '')))
                continue
        if need.get('probe'):
            code, _ = run(need['probe'], timeout=30)
            if code != 0:
                results.append((False, '%s is installed but not usable (%s failed)' % (label, ' '.join(need['probe']))))
                continue
        results.append((True, '%s found' % label))
    return results


def is_installed(app):
    spec = app.get('installed') or {}
    if spec.get('command'):
        if not shutil.which(spec['command'][0]):
            return False
        code, _ = run(spec['command'])
        return code == 0
    if spec.get('path'):
        return os.path.exists(os.path.expanduser(spec['path']))
    return None  # nothing to detect it by


def is_running(app):
    url = app.get('health')
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return r.status < 500
    except Exception as e:  # a 401 or 404 still means something is listening
        return getattr(e, 'code', 600) < 500


def steps_for(app, key):
    here = 'windows' if WINDOWS else 'posix'
    steps = [s for s in app.get(key, []) if s.get('os', 'any') in ('any', here)]
    chosen = []
    for s in steps:
        if s.get('requires') and not shutil.which(s['requires']):
            continue  # an alternative that suits this machine comes later in the list
        chosen.append(s)
        if 'run' in s or 'script' in s:
            break  # one way to install is enough
    return chosen


def describe(step):
    if 'run' in step:
        return '$ ' + ' '.join(step['run'])
    if 'script' in step:
        return 'download %s, show its checksum, run it with %s' % (step['script'], step.get('shell', 'sh'))
    return step.get('manual', '')


def fetch_script(url):
    if not url.startswith(('https://', 'file:')):
        sys.exit('refusing a script from %s: only https is allowed' % url)
    with urllib.request.urlopen(url, timeout=60) as r:
        body = r.read()
    f = tempfile.NamedTemporaryFile('wb', suffix='.sh', delete=False)
    f.write(body)
    f.close()
    return f.name, hashlib.sha256(body).hexdigest(), len(body)


def execute(step):
    if 'manual' in step:
        print(step['manual'])
        return 1
    if 'script' in step:
        path, digest, size = fetch_script(step['script'])
        print('saved %s (%d bytes, sha256 %s)' % (step['script'], size, digest))
        try:
            return subprocess.run([step.get('shell', 'sh'), path]).returncode
        finally:
            os.unlink(path)
    exe = shutil.which(step['run'][0])
    if not exe:
        print('%s is not installed' % step['run'][0])
        return 127
    return subprocess.run([exe] + step['run'][1:]).returncode


def status(app):
    lines = []
    problems = check_needs(app)
    for ok, msg in problems:
        lines.append(('ok      ' if ok and 'needed, found' not in msg else 'WARNING ' if ok else 'MISSING ') + msg)
    installed = is_installed(app)
    running = is_running(app)
    if installed is None:
        state = 'cannot tell if it is installed'
    elif installed:
        state = 'installed' + ('' if running is None else (', running' if running else ', not running'))
    else:
        state = 'not installed'
    return state, lines, all(ok for ok, _ in problems), installed, running


def cmd_list(apps):
    for key, app in apps.items():
        print('%-12s %s' % (key, app['what']))


def cmd_status(app, key):
    state, lines, ready, _installed, _running = status(app)
    print('%s: %s' % (app['name'], state))
    for line in lines:
        print('  ' + line)
    return 0 if state.startswith('installed') else 1


def cmd_install(app, key, yes, update=False):
    steps = steps_for(app, 'update' if update and app.get('update') else 'install')
    if not steps:
        print('No install step for this machine. See %s' % app.get('homepage', ''))
        return 1
    state, lines, ready, installed, _ = status(app)
    verb = 'update' if update else 'install'
    if installed and not update:
        print('%s is already installed. Use `update` to move to the newest release.' % app['name'])
        return 0
    print('Plan to %s %s (%s):' % (verb, app['name'], app.get('homepage', '')))
    for line in lines:
        print('  ' + line)
    for s in steps:
        print('  - ' + describe(s))
        if s.get('why'):
            print('    ' + s['why'])
    if app.get('provider_keys'):
        print('  Afterwards you add your own provider keys; this tool never asks for them.')
    if not ready:
        print('\nFix the missing items above first.')
        return 1
    if not yes:
        print('\nNothing was changed. Run the same command with --yes after the user agrees.')
        return 2
    for s in steps:
        code = execute(s)
        if code != 0:
            print('step failed (exit %s): %s' % (code, describe(s)))
            return 1
    for line in app.get('after', []):
        print(line)
    return 0


def cmd_start(app, key):
    if is_running(app):
        print('%s is already running.' % app['name'])
        return 0
    start = app.get('start')
    if not start:
        print('%s has no start command here. %s' % (app['name'], ' '.join(app.get('after', []))))
        return 1
    if is_installed(app) is False:
        print('%s is not installed. Run `install` first.' % app['name'])
        return 1
    exe = shutil.which(start['run'][0])
    if not exe:
        print('%s is not installed' % start['run'][0])
        return 1
    if start.get('detach'):
        kw = {'creationflags': 0x00000008} if WINDOWS else {'start_new_session': True}
        log = open(os.path.join(tempfile.gettempdir(), 'sfp-%s.log' % key), 'ab')
        subprocess.Popen([exe] + start['run'][1:], stdout=log, stderr=log, stdin=subprocess.DEVNULL, **kw)
    elif subprocess.run([exe] + start['run'][1:]).returncode != 0:
        return 1
    for _ in range(40):
        if app.get('health') is None or is_running(app):
            print('%s is running%s.' % (app['name'], (' at ' + app['health']) if app.get('health') else ''))
            return 0
        time.sleep(0.5)
    print('%s did not answer at %s within 20 seconds.' % (app['name'], app.get('health')))
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['status', 'install', 'update', 'start', 'list'])
    ap.add_argument('id', nargs='?')
    ap.add_argument('--yes', action='store_true', help='actually run the plan')
    args = ap.parse_args(argv)
    apps = load()
    if args.command == 'list':
        return cmd_list(apps) or 0
    key = args.id
    if key is None and len(apps) == 1:
        key = next(iter(apps))
    if key not in apps:
        sys.exit('say which one: %s' % ', '.join(apps))
    app = apps[key]
    if args.command == 'status':
        return cmd_status(app, key)
    if args.command == 'start':
        return cmd_start(app, key)
    return cmd_install(app, key, args.yes, update=args.command == 'update')


if __name__ == '__main__':
    sys.exit(main())
