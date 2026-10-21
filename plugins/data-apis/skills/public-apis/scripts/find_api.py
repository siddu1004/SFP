#!/usr/bin/env python3
"""Search the bundled public-apis list.

  python3 find_api.py weather                       # keyword search
  python3 find_api.py "cat facts" --auth none --cors yes
  python3 find_api.py --category Finance --https yes --limit 20
  python3 find_api.py --categories                  # list categories
  python3 find_api.py music --json                  # machine-readable

Keywords must all appear (case-insensitive) in the name, description or category.
--auth: none | apiKey | OAuth | any   --cors / --https: yes | no | unknown | any
"""
import argparse
import json
import os
import re
import sys

LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reference', 'public-apis.md')
ROW = re.compile(r'^\|\s*\[(?P<name>[^\]]+)\]\((?P<url>[^)]+)\)\s*\|(?P<desc>.*?)\|(?P<auth>[^|]*)\|(?P<https>[^|]*)\|(?P<cors>[^|]*)\|')


def load():
    apis, category = [], None
    with open(LIST, encoding='utf-8') as f:
        for line in f:
            if line.startswith('### '):
                category = line[4:].strip()
                continue
            m = ROW.match(line)
            if m and category:
                apis.append({
                    'name': m['name'].strip(), 'url': m['url'].strip(), 'description': m['desc'].strip(),
                    'auth': m['auth'].strip().strip('`') or 'No', 'https': m['https'].strip(), 'cors': m['cors'].strip(),
                    'category': category,
                })
    return apis


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('keywords', nargs='*')
    ap.add_argument('--category', help='category name or part of it')
    ap.add_argument('--auth', default='any')
    ap.add_argument('--cors', default='any')
    ap.add_argument('--https', default='any')
    ap.add_argument('--limit', type=int, default=15)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--categories', action='store_true')
    args = ap.parse_args()

    apis = load()
    if args.categories:
        names = sorted({a['category'] for a in apis})
        print('\n'.join(f"{n} ({sum(1 for a in apis if a['category'] == n)})" for n in names))
        return

    def keep(a):
        hay = f"{a['name']} {a['description']} {a['category']}".lower()
        if any(k.lower() not in hay for k in args.keywords):
            return False
        if args.category and args.category.lower() not in a['category'].lower():
            return False
        if args.auth != 'any':
            none = a['auth'].lower() == 'no'
            if (args.auth.lower() in ('none', 'no')) != none or (not none and args.auth.lower() not in ('none', 'no') and args.auth.lower() != a['auth'].lower()):
                return False
        for key in ('cors', 'https'):
            want = getattr(args, key)
            if want != 'any' and a[key].lower() != want.lower():
                return False
        return True

    hits = [a for a in apis if keep(a)]
    if args.json:
        print(json.dumps(hits[:args.limit], indent=1, ensure_ascii=False))
        return
    if not hits:
        print('No match. Try fewer or broader keywords, or --categories.')
        return
    print(f'{len(hits)} match(es); showing {min(len(hits), args.limit)}:\n')
    for a in hits[:args.limit]:
        print(f"{a['name']}  [{a['category']}]  auth={a['auth']} https={a['https']} cors={a['cors']}")
        print(f"  {a['description']}\n  {a['url']}")


if __name__ == '__main__':
    sys.exit(main())
