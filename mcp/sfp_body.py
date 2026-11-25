#!/usr/bin/env python3
"""Find skills by everything their SKILL.md says, with BM25. No model is needed.

A description is one line; the body says what the skill really does. Leaving it out costs a router 29 to 44 points
(SkillRouter, arXiv 2603.22455); here, on 175 plain tasks, the right skill is chosen for 61% instead of 58% with an
embedding model and for 52% instead of 41% with none.
The index is built once from the skill files and kept in the data folder, under a key of the files' sizes and times.
"""
import hashlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sfp_embed  # noqa: E402
import sfp_mcp as core  # noqa: E402

K1, B = 1.2, 0.75
MAX_CHARS = 20000
FRESH = 30.0             # seconds before the skill files are looked at again
_INDEX = {}


def _file(name):
    return os.path.join(core.ROOT, core.SKILLS[name]['path'], 'SKILL.md')


def _key(names):
    h = hashlib.sha1()
    for n in names:
        try:
            st = os.stat(_file(n))
            h.update(('%s %d %d\n' % (n, st.st_size, int(st.st_mtime))).encode('utf-8'))
        except OSError:
            h.update((n + ' -\n').encode('utf-8'))
    return h.hexdigest()


def cache_path():
    return os.path.join(sfp_embed.data_dir(), 'body_index.json')


def build(names):
    post, lengths = {}, []
    for i, n in enumerate(names):
        try:
            with open(_file(n), encoding='utf-8', errors='ignore') as f:
                toks = core.tokens(f.read(MAX_CHARS))
        except OSError:
            toks = []
        lengths.append(len(toks))
        count = {}
        for t in toks:
            count[t] = count.get(t, 0) + 1
        for t, c in count.items():
            post.setdefault(t, []).append([i, c])
    return {'names': names, 'len': lengths, 'post': post}


def index():
    names = sorted(core.SKILLS)
    if _INDEX.get('names') == names and time.time() - _INDEX.get('seen', 0) < FRESH:
        return _INDEX
    key = _key(names)
    if _INDEX.get('key') == key:
        _INDEX['seen'] = time.time()
        return _INDEX
    data = None
    try:
        with open(cache_path(), encoding='utf-8') as f:
            data = json.load(f)
        if data.get('key') != key:
            data = None
    except (OSError, ValueError, AttributeError):
        data = None
    if data is None:
        data = dict(build(names), key=key)
        try:
            os.makedirs(os.path.dirname(cache_path()), exist_ok=True)
            with open(cache_path() + '.tmp', 'w', encoding='utf-8') as f:
                json.dump(data, f, separators=(',', ':'))
            os.replace(cache_path() + '.tmp', cache_path())
        except OSError:
            pass
    _INDEX.clear()
    _INDEX.update(data, seen=time.time())
    return _INDEX


def search(text, limit=80):
    """[(score, skill)] best first."""
    ix = index()
    n = len(ix['names'])
    mean = (sum(ix['len']) / n) if n else 1.0
    score = {}
    for t in set(core.tokens(text or '')):
        rows = ix['post'].get(t)
        if not rows:
            continue
        idf = math.log(1 + (n - len(rows) + 0.5) / (len(rows) + 0.5))
        for i, c in rows:
            score[i] = score.get(i, 0.0) + idf * c * (K1 + 1) / (c + K1 * (1 - B + B * ix['len'][i] / (mean or 1.0)))
    top = sorted(score.items(), key=lambda kv: (-kv[1], ix['names'][kv[0]]))[:limit]
    return [(s, ix['names'][i]) for i, s in top]
