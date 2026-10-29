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
HOME = os.path.expanduser('~')
# The command each editor puts on PATH. Antigravity is a VS Code fork and ships the same kind of command.
EDITORS = {
    'antigravity': 'antigravity',
    'vscode': 'code',
    'vscode-insiders': 'code-insiders',
    'cursor': 'cursor',
    'windsurf': 'windsurf',
    'codium': 'codium',
    'kiro': 'kiro',
    'trae': 'trae',
    'qoder': 'qoder',
    'pearai': 'pearai',
    'void': 'void',
    'positron': 'positron',
}

EDITOR_ALIASES = {
    'antigravity': ['antigravity', 'antigravity-ide', 'agy'],
    'vscode': ['code'],
    'vscode-insiders': ['code-insiders'],
    'cursor': ['cursor', 'cursor-nightly'],
    'windsurf': ['windsurf', 'windsurf-next'],
    'codium': ['codium', 'vscodium'],
    'kiro': ['kiro'],
    'trae': ['trae', 'trae-cn'],
    'qoder': ['qoder'],
    'pearai': ['pearai'],
    'void': ['void'],
    'positron': ['positron'],
}


def find_editor_cli(name):
    for cmd in EDITOR_ALIASES.get(name, [EDITORS[name]]):
        exe = shutil.which(cmd)
        if exe:
            return exe
    if os.name == 'nt':
        local = os.environ.get('LOCALAPPDATA') or os.path.join(HOME, 'AppData', 'Local')
        win_dirs = {
            'antigravity': [('Antigravity IDE', 'antigravity-ide.cmd'), ('Antigravity', 'antigravity.cmd')],
            'vscode': [('Microsoft VS Code', 'code.cmd')],
            'vscode-insiders': [('Microsoft VS Code Insiders', 'code-insiders.cmd')],
            'cursor': [('cursor', 'cursor.cmd'), ('Cursor', 'cursor.cmd')],
            'windsurf': [('Windsurf', 'windsurf.cmd')],
            'codium': [('VSCodium', 'codium.cmd')],
            'kiro': [('Kiro', 'kiro.cmd')],
            'trae': [('Trae', 'trae.cmd')],
            'qoder': [('Qoder', 'qoder.cmd')],
            'pearai': [('PearAI', 'pearai.cmd')],
            'void': [('Void', 'void.cmd')],
            'positron': [('Positron', 'positron.cmd')],
        }
        for folder, script in win_dirs.get(name, []):
            cand = os.path.join(local, 'Programs', folder, 'bin', script)
            if os.path.isfile(cand):
                return cand
    elif sys.platform == 'darwin':
        mac_apps = {
            'antigravity': [('Antigravity.app', 'antigravity'), ('Antigravity IDE.app', 'antigravity-ide')],
            'vscode': [('Visual Studio Code.app', 'code')],
            'vscode-insiders': [('Visual Studio Code - Insiders.app', 'code-insiders')],
            'cursor': [('Cursor.app', 'cursor')],
            'windsurf': [('Windsurf.app', 'windsurf')],
            'codium': [('VSCodium.app', 'codium')],
            'kiro': [('Kiro.app', 'kiro')],
            'trae': [('Trae.app', 'trae')],
            'qoder': [('Qoder.app', 'qoder')],
            'pearai': [('PearAI.app', 'pearai')],
            'void': [('Void.app', 'void')],
            'positron': [('Positron.app', 'positron')],
        }
        for app, bin_name in mac_apps.get(name, []):
            for root in ('/Applications', os.path.join(HOME, 'Applications')):
                cand = os.path.join(root, app, 'Contents', 'Resources', 'app', 'bin', bin_name)
                if os.path.isfile(cand):
                    return cand
    return None


def clean_stale_extensions():
    for stale in glob.glob(os.path.join(HOME, '.*', 'extensions', 'sfp.sfp-hive-extension-*')):
        if os.path.isdir(stale) and not os.path.isfile(os.path.join(stale, 'out', 'extension.js')):
            shutil.rmtree(stale, ignore_errors=True)


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
    clean_stale_extensions()
    wanted = [args.editor] if args.editor else sorted(EDITORS)
    done = []
    for name in wanted:
        exe = find_editor_cli(name)
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
