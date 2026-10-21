#!/usr/bin/env python3
"""Run the SFP skill selector from wherever this skill was installed.

Finds the SFP checkout, then hands every argument to mcp/sfp_hive.py:
  python3 select_skills.py select "add tests for the checkout form" --project .
  python3 select_skills.py feedback last --helped django-tdd --unhelpful django-celery
  python3 select_skills.py status
"""
import os
import runpy
import sys


def find_root():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [os.environ.get('SFP_ROOT')]
    pointer = os.path.join(os.path.expanduser('~'), '.sfp', 'root')
    if os.path.isfile(pointer):
        with open(pointer, encoding='utf-8') as f:
            candidates.append(f.read().strip())
    candidates.append(os.path.join(os.path.expanduser('~'), '.claude', 'plugins', 'marketplaces', 'sfp'))
    d = here
    for _ in range(6):  # inside a checkout: plugins/sfp/skills/sfp-hive/scripts
        d = os.path.dirname(d)
        candidates.append(d)
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, 'mcp', 'sfp_hive.py')) and os.path.isfile(os.path.join(c, 'catalog.json')):
            return os.path.abspath(c)
    sys.exit('Cannot find the SFP checkout. Install SFP (its installer writes ~/.sfp/root) or set SFP_ROOT.')


if __name__ == '__main__':
    root = find_root()
    os.environ['SFP_ROOT'] = root
    engine = os.path.join(root, 'mcp', 'sfp_hive.py')
    sys.argv = [engine] + sys.argv[1:]
    sys.path.insert(0, os.path.dirname(engine))
    runpy.run_path(engine, run_name='__main__')
