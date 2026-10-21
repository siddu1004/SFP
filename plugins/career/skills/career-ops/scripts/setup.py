#!/usr/bin/env python3
"""Set up career-ops for SFP.

Clones the original career-ops project at a pinned commit into
~/.sfp/apps/career-ops (or $CAREER_OPS_HOME) and applies SFP's patch, which keeps
your CV, tracker and reports in ~/career-ops so updates never touch them.
Safe to run again: it updates the checkout to the pinned commit and reapplies the patch.

  python3 setup.py                 set up or update
  python3 setup.py --dir PATH      use another folder
  python3 setup.py --status        say what state the checkout is in
"""
import argparse
import os
import subprocess
import sys

COMMIT = '09a554802d4254942aeaf151682e3c824fc2684b'
REPO = 'https://github.com/career-ops-hq/career-ops.git'
HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.normpath(os.path.join(HERE, '..', 'patches', 'data-root.patch'))


def git(dest, *args, **kw):
    check = kw.get('check', True)
    done = subprocess.run(['git', '-C', dest] + list(args), capture_output=True, text=True)
    if check and done.returncode != 0:
        sys.exit('git %s failed:\n%s' % (' '.join(args), (done.stderr or done.stdout).strip()))
    return done


def patch_applied(dest):
    return git(dest, 'apply', '--reverse', '--check', PATCH, check=False).returncode == 0


def head(dest):
    return git(dest, 'rev-parse', 'HEAD', check=False).stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', default=os.environ.get('CAREER_OPS_HOME') or os.path.join(os.path.expanduser('~'), '.sfp', 'apps', 'career-ops'))
    ap.add_argument('--status', action='store_true')
    args = ap.parse_args()
    dest = os.path.abspath(os.path.expanduser(args.dir))

    if not os.path.isfile(PATCH):
        sys.exit('missing patch file: %s' % PATCH)
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        sys.exit('git is required: https://git-scm.com/downloads')

    exists = os.path.isdir(os.path.join(dest, '.git'))
    if args.status:
        if not exists:
            print('not set up (no checkout at %s)' % dest)
        else:
            print('checkout: %s\nat pinned commit: %s\npatch applied: %s' % (dest, head(dest) == COMMIT, patch_applied(dest)))
        return

    if not exists:
        if os.path.exists(dest) and os.listdir(dest):
            sys.exit('%s exists and is not a career-ops checkout. Pick another folder with --dir.' % dest)
        os.makedirs(dest, exist_ok=True)
        subprocess.run(['git', 'init', '-q', dest], check=True)
        git(dest, 'remote', 'add', 'origin', REPO)
    elif patch_applied(dest):
        git(dest, 'apply', '--reverse', PATCH)  # back to pristine so the checkout can move

    if head(dest) != COMMIT:
        print('fetching career-ops %s ...' % COMMIT[:9])
        git(dest, 'fetch', '-q', '--depth', '1', 'origin', COMMIT)
        git(dest, 'checkout', '-q', 'FETCH_HEAD')

    if not patch_applied(dest):
        git(dest, 'apply', PATCH)

    print('career-ops is ready in %s (commit %s, SFP data-safety patch applied).' % (dest, COMMIT[:9]))
    print('Next, once: cd "%s" && npm install' % dest)
    print('For browser modes also: npx playwright install chromium')
    print('Your CV, tracker and reports are kept in %s.' % os.path.join(os.path.expanduser('~'), 'career-ops'))


if __name__ == '__main__':
    main()
