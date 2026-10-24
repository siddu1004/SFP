#!/usr/bin/env python3
"""Check, from the command line, that the SFP Hive extension is installed in an editor and can work.

  python3 verify.py                     look in every VS Code style editor found
  python3 verify.py --editor antigravity
  python3 verify.py --json              the same, as JSON (for an agent to read back)

It checks what a command can check: the editor command, the installed extension, the SFP checkout, the hive,
the learning log, and the editor's extension-host logs for errors from this extension. What it cannot check is
what is drawn on screen; the checklist in docs/ANTIGRAVITY.md covers that. Exit code 1 if any check FAILs.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

EXT_ID = 'siddu1004.sfp-hive'
EDITORS = {'antigravity': 'antigravity', 'vscode': 'code', 'cursor': 'cursor', 'windsurf': 'windsurf', 'codium': 'codium'}
HOME = os.path.expanduser('~')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PASS, FAIL, WARN, SKIP = 'PASS', 'FAIL', 'WARN', 'SKIP'


def find_installed(home=HOME):
    """Folders of the installed extension, in any editor's extensions folder (~/.<editor>/extensions)."""
    return sorted(glob.glob(os.path.join(home, '.*', 'extensions', EXT_ID + '-*')))


def log_files(home=HOME):
    """Extension-host logs the editors write, wherever the platform keeps them."""
    roots = [os.path.join(home, '.config'), os.path.join(home, 'Library', 'Application Support'),
             os.environ.get('APPDATA') or os.path.join(home, 'AppData', 'Roaming')]
    files = []
    for root in roots:
        files += glob.glob(os.path.join(root, '*', 'logs', '*', '*', 'exthost*', '*.log'))
        files += glob.glob(os.path.join(root, '*', 'logs', '*', 'exthost*', '*.log'))
        files += glob.glob(os.path.join(root, '*', 'logs', '*', '*', 'exthost*', '*', '*.log'))
    return sorted(set(files), key=os.path.getmtime, reverse=True)[:40]


def scan_logs(files):
    """(lines that mention this extension, those among them that look like errors)."""
    mentions, errors = [], []
    for path in files:
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                for line in f:
                    if EXT_ID in line or 'sfp-hive' in line.lower():
                        mentions.append(line.strip()[:200])
                        if any(w in line.lower() for w in ('error', 'cannot find', 'failed', 'exception')):
                            errors.append(line.strip()[:200])
        except OSError:
            continue
    return mentions, errors


def check_hive(root, python=sys.executable):
    """Run the real hive once and return the parsed answer."""
    env = dict(os.environ, SFP_DATA_DIR=tempfile.mkdtemp(prefix='sfp-verify-'))
    env.pop('SFP_NO_USAGE_LOG', None)
    done = subprocess.run([python, os.path.join(root, 'mcp', 'sfp_hive.py'), 'select', 'write table driven tests for a go parser',
                           '--json', '--max', '3'], capture_output=True, text=True, timeout=180, env=env)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or done.stdout).strip().splitlines()[-1:] or 'failed')
    return json.loads(done.stdout)


def sfp_root(home=HOME):
    for cand in (os.environ.get('SFP_ROOT'), open(os.path.join(home, '.sfp', 'root')).read().strip() if os.path.isfile(os.path.join(home, '.sfp', 'root')) else None, REPO):
        if cand and os.path.isfile(os.path.join(cand, 'mcp', 'sfp_hive.py')):
            return cand
    return None


def run_checks(editor=None, home=HOME):
    results = []

    def add(name, status, detail=''):
        results.append({'check': name, 'status': status, 'detail': detail})

    names = [editor] if editor else sorted(EDITORS)
    clis = {n: shutil.which(EDITORS[n]) for n in names}
    found = {n: p for n, p in clis.items() if p}
    add('editor command on PATH', PASS if found else FAIL,
        ', '.join('%s (%s)' % (n, p) for n, p in found.items()) or 'none of: ' + ', '.join(EDITORS[n] for n in names) +
        '. In the editor run "Shell Command: Install \'<editor>\' command in PATH", or install the .vsix from the Extensions view.')

    for n, exe in found.items():
        try:
            first = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=60).stdout.split()
            parts = [int(x) for x in first[0].split('.')[:2]] if first else []
            need = [int(x) for x in json.load(open(os.path.join(HERE, 'package.json')))['engines']['vscode'].lstrip('^').split('.')[:2]]
            add('editor is new enough (%s)' % n, PASS if parts >= need else FAIL, 'editor %s, the extension needs VS Code %s or newer' % (first[0] if first else '?', '.'.join(map(str, need))))
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            add('editor is new enough (%s)' % n, WARN, 'could not read its version')
    listed = {}
    for n, exe in found.items():
        try:
            out = subprocess.run([exe, '--list-extensions', '--show-versions'], capture_output=True, text=True, timeout=60).stdout
            listed[n] = [l for l in out.splitlines() if l.lower().startswith(EXT_ID)]
        except (OSError, subprocess.SubprocessError) as e:
            listed[n] = []
            add('list extensions (%s)' % n, WARN, str(e))
    if found:
        hit = {n: v for n, v in listed.items() if v}
        add('extension listed by the editor', PASS if hit else FAIL,
            '; '.join('%s: %s' % (n, v[0]) for n, v in hit.items()) or '%s not in any editor\'s list. Run python3 install.py' % EXT_ID)

    folders = find_installed(home)
    add('extension folder on disk', PASS if folders else FAIL, ', '.join(folders) or 'no ~/.<editor>/extensions/%s-*' % EXT_ID)
    if folders:
        try:
            pkg = json.load(open(os.path.join(folders[-1], 'package.json')))
            ok = 'onStartupFinished' in pkg.get('activationEvents', []) and os.path.isfile(os.path.join(folders[-1], pkg['main']))
            add('installed copy activates at startup and has its code', PASS if ok else FAIL,
                'version %s; an older build lacks startup activation, so the status-bar item would be missing' % pkg.get('version'))
        except (OSError, ValueError, KeyError) as e:
            add('installed copy activates at startup and has its code', FAIL, str(e))

    root = sfp_root(home)
    add('SFP checkout found', PASS if root else FAIL, root or 'set SFP_ROOT, or run the SFP installer so ~/.sfp/root exists')
    if root:
        try:
            sel = check_hive(root)
            add('the hive answers', PASS if sel.get('stack') else FAIL, 'chose: ' + ', '.join(s['name'] for s in sel['stack']))
        except Exception as e:  # noqa: BLE001 - report whatever went wrong
            add('the hive answers', FAIL, str(e))

    for var in ('SFP_NO_USAGE_LOG', 'SFP_NO_LEARNING'):
        if os.environ.get(var):
            add('learning is on (%s)' % var, WARN, '%s is set in this shell, so feedback is not recorded here. The editor has its own environment.' % var)
    data = os.environ.get('SFP_DATA_DIR') or os.path.join(home, '.sfp')
    add('feedback log folder is writable', PASS if os.access(data if os.path.isdir(data) else home, os.W_OK) else FAIL, data)

    files = log_files(home)
    if not files:
        add('editor logs show the extension starting', SKIP, 'no extension-host logs found; open the editor once, then run this again')
    else:
        mentions, errors = scan_logs(files)
        if errors:
            add('editor logs show the extension starting', FAIL, 'errors mentioning the extension: ' + ' | '.join(errors[:3]))
        elif mentions:
            add('editor logs show the extension starting', PASS, '%d log lines mention it, no errors' % len(mentions))
        else:
            add('editor logs show the extension starting', WARN, 'logs found but nothing mentions the extension; reload the window and run this again')
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--editor', choices=sorted(EDITORS))
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    results = run_checks(args.editor)
    if args.json:
        print(json.dumps(results, indent=1))
    else:
        for r in results:
            print('%-4s  %s%s' % (r['status'], r['check'], ('\n        ' + r['detail']) if r['detail'] else ''))
        bad = [r for r in results if r['status'] == FAIL]
        print('\n%d checks, %d failed. Now do the on-screen checklist in docs/ANTIGRAVITY.md.' % (len(results), len(bad)))
    sys.exit(1 if any(r['status'] == FAIL for r in results) else 0)


if __name__ == '__main__':
    main()
