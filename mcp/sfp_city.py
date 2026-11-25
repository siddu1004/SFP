#!/usr/bin/env python3
"""The skill city: every skill is a building with a story, every way of reading a task draws a map of heights over the
buildings, and a learned selector reads all the maps.

  story     what a building is: what the skill does, the words that call it, its district (category) and tower (cluster),
            the job it does, what it makes, what it needs and how many tokens it costs.
  maps      one per reader: words, name, full text, requests, story, and with an embedding model the description, the
            closest request, the closest three requests and the two together. A building's height on a map is its rank
            there, 21 / (21 + rank), next to how far it rises above the sixtieth building.
  towers    neighbours lend each other height: a building among tall ones is more likely right than one that stands alone.
  selector  a softmax policy p(skill) = exp(5 w.f) / sum, where f are the heights. The shipped weights were trained on
            tests/plain_tuning.json and search_reworded.json only (scripts/make_city.py). Feedback moves them on this
            machine by the policy gradient of the expected reward, held near the shipped weights, so a few wrong reports
            cannot ruin them.

The coding agent gets the map too (the best 40, in towers): the right skill is on it far more often than among the few
picks, and the agent can read the towers and choose better than any local score.

Pure standard library. The log keeps skill names and numbers, never the task.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sfp_body  # noqa: E402
import sfp_embed  # noqa: E402
import sfp_mcp as core  # noqa: E402

CITY_FILE = os.path.join(core.ROOT, 'skill_city.json')
TEXT_MAPS = ('words', 'name', 'body', 'keys', 'story')
MEANING_MAPS = ('doc', 'exmax', 'exmean', 'meaning')
POOL = 80                # buildings the selector scores
MAP_SIZE = 40            # buildings on the map the agent reads
RANK_K = 21
TEMPER = 5.0
KEEP = 20                # buildings kept in the log for learning
RATE, PULL, REACH = 0.05, 0.05, 0.4   # learning step, pull back to the shipped weights, furthest a weight may move
_DATA = {}
_HOMES = {}


def data():
    if not _DATA:
        try:
            with open(CITY_FILE, encoding='utf-8') as f:
                _DATA.update(json.load(f))
        except (OSError, ValueError):
            _DATA.update({'keys': {}, 'near': {}, 'weights': {}})
    return _DATA


# ---- stories -----------------------------------------------------------------------------------------------------

def _homes():
    if not _HOMES:
        import sfp_clusters
        _HOMES.update(sfp_clusters.assign())
    return _HOMES


def story(name):
    """What a building is, for people, agents and the maps. {} for an unknown skill."""
    s = core.SKILLS.get(name)
    if not s:
        return {}
    import sfp_cards
    import sfp_stack as v1
    card = sfp_cards.get_card(name)
    home = _homes().get(name) or ['other-' + s['category']]
    return {'name': name, 'does': ' '.join((s.get('description') or '').split()),
            'activates_on': data().get('keys', {}).get(name, []), 'district': s['category'], 'tower': home[0],
            'job': card.get('job'), 'makes': card.get('output') or [], 'needs': card.get('needs') or [],
            'tech': sorted(v1.SKILL_TECH.get(name, set())),
            'next_to': [n for n, _ in data().get('near', {}).get(name, [])][:3], 'tokens': v1.body_tokens(name)}


# ---- maps --------------------------------------------------------------------------------------------------------

def maps(task, meaning=None):
    """{map name: {skill: raw height}}. `meaning` is sfp_embed.survey's answer; {} leaves the meaning maps out."""
    out = {'words': {s['name']: v for v, s in core.scored_search(task, limit=80)}}
    for field in ('name', 'body', 'keys', 'story'):
        out[field] = sfp_body.scores(task, field)
    if meaning:
        out['doc'] = {n: v[0] for n, v in meaning.items()}
        out['exmax'] = {n: v[1] for n, v in meaning.items() if v[1] is not None}
        out['exmean'] = {n: v[2] for n, v in meaning.items() if v[2] is not None}
        out['meaning'] = {n: (0.5 * v[0] + 0.5 * v[1]) if v[1] is not None else v[0] for n, v in meaning.items()}
    return out


def _heights(raw):
    """({skill: rank height}, {skill: how far it rises above the sixtieth, 0 to 1}) for one map."""
    order = sorted(raw.items(), key=lambda kv: (-kv[1], kv[0]))
    if not order:
        return {}, {}
    rank_height = {n: RANK_K / (RANK_K + i) for i, (n, _) in enumerate(order)}
    top, floor = order[0][1], (order[59][1] if len(order) > 59 else 0.0)
    span = top - floor + 1e-6
    return rank_height, {n: min(1.0, max(0.0, (v - floor) / span)) for n, v in order[:60]}


def features(task, meaning=None, allow=None):
    """(kind, pool, {skill: [features]}): the buildings worth scoring and their heights on every map."""
    kind = 'model' if meaning else 'text'
    use = TEXT_MAPS + (MEANING_MAPS if meaning else ())
    got = maps(task, meaning)
    high, rise = {}, {}
    for m in use:
        high[m], rise[m] = _heights(got.get(m) or {})
    main = [m for m in ('body', 'meaning', 'story') if m in use]
    base, total = {}, {}
    for m in main:
        for n, v in high[m].items():
            base[n] = base.get(n, 0.0) + v / len(main)
    for m in use:
        if m != 'name':
            for n, v in high[m].items():
                total[n] = total.get(n, 0.0) + v
    pool = [n for n in sorted(total, key=lambda n: (-total[n], n)) if n in core.SKILLS and (allow is None or allow(n))][:POOL]
    near, out = data().get('near', {}), {}
    for n in pool:
        lent = sum(w * base.get(o, 0.0) for o, w in near.get(n, ()))
        tall = sum(1 for m in use if high[m].get(n, 0.0) > RANK_K / (RANK_K + 10)) / len(use)
        out[n] = ([high[m].get(n, 0.0) for m in use] + [rise[m].get(n, 0.0) for m in use]
                  + [lent, lent * base.get(n, 0.0), tall])
    return kind, pool, out


# ---- selector ----------------------------------------------------------------------------------------------------

def _weights_path():
    return os.path.join(sfp_embed.data_dir(), 'city_weights.json')


def _log_path():
    return os.path.join(sfp_embed.data_dir(), 'city_log.jsonl')


def learning():
    return not (os.environ.get('SFP_NO_LEARNING') or os.environ.get('SFP_NO_USAGE_LOG'))


def shipped_weights(kind, size):
    w = data().get('weights', {}).get(kind) or []
    return w if len(w) == size else [0.15] * size


def weights(kind, size):
    """The weights of a kind: this user's when they fit, else the shipped ones, else equal."""
    shipped = shipped_weights(kind, size)
    if not learning():
        return shipped
    try:
        with open(_weights_path(), encoding='utf-8') as f:
            mine = json.load(f).get(kind) or []
        if len(mine) == size and all(abs(a - b) <= REACH + 1e-4 for a, b in zip(mine, shipped)):
            return mine
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return shipped


def rank(task, meaning=None, allow=None):
    """(skills best first, {skill: height}, kind, {skill: features})."""
    kind, pool, f = features(task, meaning, allow)
    if not pool:
        return [], {}, kind, {}
    w = weights(kind, len(f[pool[0]]))
    score = {n: sum(a * b for a, b in zip(w, f[n])) for n in pool}
    return sorted(pool, key=lambda n: (-score[n], n)), score, kind, f


def policy(score):
    """{skill: probability}: the softmax policy over the pool."""
    if not score:
        return {}
    top = max(score.values())
    e = {n: math.exp(TEMPER * (s - top)) for n, s in score.items()}
    z = sum(e.values())
    return {n: v / z for n, v in e.items()}


def _brief(name, limit=90):
    d = ' '.join((core.SKILLS[name].get('description') or '').split())
    return d if len(d) <= limit else d[:limit].rsplit(' ', 1)[0].rstrip(' ,;:.') + '...'


def towers(order, score, size=MAP_SIZE, skip=()):
    """The map: the best `size` buildings grouped into towers, tallest first. A tower's height is the probability its
    buildings hold together; inside it the floors are in order."""
    import sfp_clusters
    names = {r['id']: r['name'] for r in sfp_clusters.shared_rules()}
    p, out = policy(score), {}
    for n in [n for n in order if n not in skip][:size]:
        tid = (_homes().get(n) or ['other'])[0]
        t = out.setdefault(tid, {'tower': names.get(tid, tid.replace('-', ' ')), 'height': 0.0, 'floors': []})
        t['height'] += p.get(n, 0.0)
        t['floors'].append({'name': n, 'does': _brief(n)})
    rows = sorted(out.values(), key=lambda t: -t['height'])
    for t in rows:
        t['height'] = round(t['height'], 3)
    return rows


def format_map(rows):
    lines = ['City map (if a pick does not fit, choose from here; tallest tower first):']
    for t in rows:
        lines.append('  ' + t['tower'])
        lines += ['    %s: %s' % (x['name'], x['does']) for x in t['floors']]
    return '\n'.join(lines)


# ---- learning ----------------------------------------------------------------------------------------------------

def seen(order, kind, f):
    """What remember() keeps of a ranking."""
    top = order[:KEEP]
    return {'kind': kind, 'names': top, 'f': [[round(x, 4) for x in f[n]] for n in top]}


def remember(decision, view):
    """Keep the heights a decision was made from, so feedback on it can teach the selector."""
    if not decision or not view or not view.get('names') or not learning():
        return
    try:
        os.makedirs(sfp_embed.data_dir(), exist_ok=True)
        row = {'t': int(time.time()), 'decision': decision, 'kind': view['kind'], 'names': view['names'], 'f': view['f']}
        with open(_log_path(), 'a', encoding='utf-8') as f:
            f.write(json.dumps(row, separators=(',', ':')) + '\n')
        if os.path.getsize(_log_path()) > 4000000:
            with open(_log_path(), encoding='utf-8') as f:
                tail = f.readlines()[-400:]
            with open(_log_path(), 'w', encoding='utf-8') as f:
                f.writelines(tail)
    except OSError:
        pass


def recall(decision):
    row = None
    try:
        with open(_log_path(), encoding='utf-8') as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get('decision') == decision:
                    row = r
    except OSError:
        pass
    return row


def update(w, shipped, names, f, reward):
    """One policy-gradient step on the expected reward of the pick, pulled towards the shipped weights and kept near them."""
    p = policy({n: sum(a * b for a, b in zip(w, v)) for n, v in zip(names, f)})
    expected = sum(p[n] * reward.get(n, 0.0) for n in names)
    grad = [0.0] * len(w)
    for n, v in zip(names, f):
        g = TEMPER * p[n] * (reward.get(n, 0.0) - expected)
        for i, x in enumerate(v):
            grad[i] += g * x
    return [round(min(s + REACH, max(s - REACH, a + RATE * g - PULL * (a - s))), 5) for a, s, g in zip(w, shipped, grad)]


def learn(decision, good=(), bad=()):
    """Feedback on a decision: good skills (helped or missing) earn 1, bad ones -1. Returns True when the weights moved."""
    row = recall(decision) if learning() else None
    if not row or not row.get('f'):
        return False
    reward = {n: 1.0 for n in good if n in row['names']}
    reward.update({n: -1.0 for n in bad if n in row['names']})
    if not reward:
        return False
    size = len(row['f'][0])
    new = update(weights(row['kind'], size), shipped_weights(row['kind'], size), row['names'], row['f'], reward)
    try:
        with open(_weights_path(), encoding='utf-8') as f:
            mine = json.load(f)
        if not isinstance(mine, dict):
            mine = {}
    except (OSError, ValueError):
        mine = {}
    mine[row['kind']] = new
    try:
        with open(_weights_path() + '.tmp', 'w', encoding='utf-8') as f:
            json.dump(mine, f)
        os.replace(_weights_path() + '.tmp', _weights_path())
    except OSError:
        return False
    return True
