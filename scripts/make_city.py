#!/usr/bin/env python3
"""Build skill_city.json: each skill's calling words, its neighbours in meaning, and the selector's weights.

Needs numpy and an embedding model (bge-m3 in Ollama) with the cache built: python3 mcp/sfp_embed.py build.
The weights are trained on tests/plain_tuning.json and tests/search_reworded.json only. Held-out sets are never read here.

  make_city.py            build everything
  make_city.py --weights  keep the words and neighbours, train the weights again
"""
import json
import math
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))
import sfp_city  # noqa: E402
import sfp_embed  # noqa: E402
import sfp_mcp as core  # noqa: E402

TUNING = ('plain_tuning', 'search_reworded')
NEIGHBOURS, SHARPNESS, WORDS = 8, 0.05, 12
L2, EPOCHS, RATE, START = 0.1, 300, 0.05, 0.15
COMMON = frozenset('the and for with your you that this from into use when how what can are help need want make using have not '
                   'get all any our its user users skill skills about should which without before after more than them they'.split())


def unit(m):
    return m / (np.linalg.norm(m, axis=-1, keepdims=True) + 1e-9)


def calling_words(names, requests):
    """The words that call a skill: frequent in its name, description and requests, rare in other skills'."""
    texts = {n: [x.strip('.') for x in re.findall(r'[a-z][a-z0-9+#.]{2,}', (n.replace('-', ' ') + ' ' + (core.SKILLS[n].get('description') or '')
                                                                         + ' ' + ' '.join(requests.get(n, []))).lower())] for n in names}
    df = {}
    for t in texts.values():
        for x in set(t):
            df[x] = df.get(x, 0) + 1
    out = {}
    for n in names:
        count = {}
        for x in texts[n]:
            if x not in COMMON and len(x) > 2:
                count[x] = count.get(x, 0) + 1
        out[n] = sorted(count, key=lambda x: (-count[x] * math.log(len(names) / df[x]), x))[:WORDS]
    return out


def neighbours(model):
    docs = {n: v[1] for n, v in sfp_embed.load_cache(model).items() if n in core.SKILLS}
    exs = {n: v[1] for n, v in sfp_embed.load_cache(model, kind='examples').items() if n in docs and len(v[1])}
    names = sorted(docs)
    d = unit(np.array([docs[n] for n in names], dtype=np.float32))
    c = np.stack([unit(unit(np.array(exs[n], dtype=np.float32)).mean(0)) if n in exs else d[i] for i, n in enumerate(names)])
    g = (d @ d.T + c @ c.T) / 2
    np.fill_diagonal(g, -1)
    out = {}
    for i, n in enumerate(names):
        top = np.argsort(-g[i])[:NEIGHBOURS]
        w = np.exp((g[i, top] - g[i, top].max()) / SHARPNESS)
        w /= w.sum()
        out[n] = [[names[j], round(float(x), 4)] for j, x in zip(top, w)]
    return out


def cases():
    out = []
    for name in TUNING:
        with open(os.path.join(ROOT, 'tests', name + '.json'), encoding='utf-8') as f:
            d = json.load(f)
        out += [(c['task'], {x for x in c['expect'] if x in core.SKILLS}) for c in (d if isinstance(d, list) else d['cases']) if c.get('expect')]
    return out


def train(rows, l2=L2):
    """Listwise softmax weights over [(features, reward)]."""
    rows = [(f, r) for f, r in rows if r.any()]
    size = rows[0][0].shape[1]
    w = np.full(size, START)
    w0, m, v = w.copy(), np.zeros(size), np.zeros(size)
    for t in range(1, EPOCHS + 1):
        g = l2 * (w - w0)
        for f, r in rows:
            s = f @ w * sfp_city.TEMPER
            p = np.exp(s - s.max())
            p /= p.sum()
            q = p * r
            q /= q.sum()
            g -= sfp_city.TEMPER * f.T @ (q - p) / len(rows)
        m, v = 0.9 * m + 0.1 * g, 0.999 * v + 0.001 * g * g
        w = w - RATE * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
    return w


def rows_for(tasks, with_model):
    out = []
    for task, want in tasks:
        meaning = sfp_embed.survey(task) if with_model else {}
        if with_model and not meaning:
            raise SystemExit('no embedding model answers')
        _, pool, f = sfp_city.features(task, meaning)
        out.append((np.array([f[n] for n in pool], dtype=np.float64), np.array([n in want for n in pool], dtype=np.float64), pool, want))
    return out


def hits(rows, w, k):
    return 100.0 * np.mean([bool({pool[i] for i in np.argsort(-(f @ w), kind='stable')[:k]} & want) for f, _, pool, want in rows])


def main():
    old = sfp_city.data() if '--weights' in sys.argv else {}
    ep = sfp_embed.find_endpoint()
    if not ep:
        raise SystemExit('start an embedding model first (see sfp_embed.py status)')
    out = {'_note': 'Built by scripts/make_city.py. keys: the words that call a skill. near: its neighbours in meaning. weights: the selector.',
           'keys': old.get('keys') or calling_words(sorted(core.SKILLS), sfp_embed.load_examples()),
           'near': old.get('near') or neighbours(ep['model'])}
    sfp_city._DATA.clear()
    sfp_city._DATA.update(dict(out, weights={}))
    out['weights'], tasks = {}, cases()
    folds = np.array_split(np.random.default_rng(0).permutation(len(tasks)), 5)
    for kind in ('text', 'model'):
        rows = rows_for(tasks, kind == 'model')
        cv = []
        for fold in folds:
            w = train([r[:2] for i, r in enumerate(rows) if i not in set(fold)])
            cv.append([hits([rows[i] for i in fold], w, k) for k in (1, 3, 10, 40)])
        print('%s, 5-fold on tuning: @1 %.1f @3 %.1f @10 %.1f @40 %.1f' % ((kind,) + tuple(np.mean(cv, 0))), flush=True)
        out['weights'][kind] = [round(float(x), 4) for x in train([r[:2] for r in rows])]
    with open(sfp_city.CITY_FILE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, separators=(',', ':'), ensure_ascii=False)
        f.write('\n')
    print('%s: %d skills, %.0f KB' % (sfp_city.CITY_FILE, len(out['keys']), os.path.getsize(sfp_city.CITY_FILE) / 1024))


if __name__ == '__main__':
    main()
