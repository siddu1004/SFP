#!/usr/bin/env python3
"""The user's own skills (~/.sfp/skills): the ones they approved from research or made from a repository.

They are not in the shipped catalog, so the city does not hold them. They are matched on their own name and description:
the share of the task's distinctive words the skill covers. Drafts are never matched: only what the user approved.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sfp_embed  # noqa: E402
import sfp_mcp as core  # noqa: E402

MIN_COVER, MIN_WORDS = 0.5, 2
MAX_BYTES = 400000


def folder():
    return os.path.join(sfp_embed.data_dir(), 'skills')


def own():
    """{name: {'path', 'does'}} of the approved skills."""
    out, base = {}, folder()
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        path = os.path.join(base, name, 'SKILL.md')
        if name == 'drafts' or not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                head = f.read(3000)
        except OSError:
            continue
        m = re.search(r'^description:\s*(.+)$', head, re.M)
        does = m.group(1).strip().strip('"').replace('\\"', '"') if m else ''
        does = re.sub(r'\[[^\]]*\]\([^)]*\)', ' ', does)                # badges and links say nothing about the skill
        out[name] = {'path': path, 'does': ' '.join(does.split())}
    return out


def _weight(token):
    n = len(core.CATALOG['skills'])
    return math.log(1 + n / (1 + core.DF.get(token, 0)))


def match(task, limit=2):
    """[{'name', 'does', 'path', 'cover'}] of the approved skills that fit the task, best first."""
    words = set(core.tokens(task or ''))
    total = sum(_weight(t) for t in words)
    out = []
    if not total:
        return out
    for name, s in own().items():
        hit = words & set(core.tokens(name.replace('-', ' ') + ' ' + s['does']))
        cover = sum(_weight(t) for t in hit) / total
        if len(hit) >= MIN_WORDS and cover >= MIN_COVER:
            out.append({'name': name, 'does': s['does'][:160], 'path': s['path'], 'cover': round(cover, 2)})
    return sorted(out, key=lambda r: (-r['cover'], r['name']))[:limit]


def read(name):
    """The SKILL.md of an approved skill, or None."""
    s = own().get(name or '')
    if not s:
        return None
    with open(s['path'], encoding='utf-8', errors='replace') as f:
        return f.read(MAX_BYTES)
