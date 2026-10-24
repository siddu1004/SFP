#!/usr/bin/env python3
"""Build the SFP Hive extension and install it into Antigravity (or any VS Code fork).

  python3 install.py                    build, test, package, then install into every editor found
  python3 install.py --editor antigravity
  python3 install.py --build-only       stop after writing the .vsix
  python3 install.py --no-test

It uses only the editor's own `--install-extension` command, so nothing inside the editor is modified. If
no editor command is on your PATH it prints the manual steps instead. Needs Node.js 18 or newer and npm.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The command each editor puts on PATH. Antigravity is a VS Code fork and ships the same kind of command.
EDITORS = {'antigravity': 'antigravity', 'vscode': 'code', 'cursor': 'cursor', 'windsurf': 'windsurf', 'codium': 'codium'}


def run(cmd):
    print('$ ' + ' '.join(cmd))
    npm_like = os.name == 'nt' and cmd[0] in ('npm', 'npx')
    done = subprocess.run(cmd, cwd=HERE, shell=npm_like)
    if done.returncode != 0:
        sys.exit('failed: ' + ' '.join(cmd))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--editor', choices=sorted(EDITORS), help='install into this editor only')
    ap.add_argument('--build-only', action='store_true')
    ap.add_argument('--no-test', action='store_true')
    args = ap.parse_args()
    if not shutil.which('npm'):
        sys.exit('npm is required (Node.js 18 or newer): https://nodejs.org/')
    if not os.path.isdir(os.path.join(HERE, 'node_modules')):
        run(['npm', 'install', '--no-audit', '--no-fund'])
    run(['npm', 'run', 'compile' if args.no_test else 'test'])
    for old in glob.glob(os.path.join(HERE, '*.vsix')):
        os.remove(old)
    run(['npx', 'vsce', 'package', '--no-dependencies'])
    vsix = sorted(glob.glob(os.path.join(HERE, '*.vsix')))[-1]
    print('built ' + vsix)
    if args.build_only:
        return
    wanted = [args.editor] if args.editor else sorted(EDITORS)
    done = []
    for name in wanted:
        exe = shutil.which(EDITORS[name])
        if not exe and name == 'antigravity':
            exe = shutil.which('antigravity-ide')
        if exe:
            run([exe, '--install-extension', vsix, '--force'])
            done.append(name)
    if done:
        print('installed into: ' + ', '.join(done) + '. Reload the window, then open the SFP Hive view in the activity bar.')
    else:
        print('No editor command found on PATH. Install by hand:\n'
              '  1. Open the editor, then the Extensions view.\n'
              '  2. Open the "..." menu and choose "Install from VSIX...".\n'
              '  3. Pick ' + vsix + ' and reload the window.')


if __name__ == '__main__':
    main()
