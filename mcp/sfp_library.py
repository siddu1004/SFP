"""The skill library: every skill by what it is trying to do (its purpose), its cluster, and bundles of skills.

Purposes come from `purposes.json`, clusters from `clusters.json` (sfp_clusters.py), and bundles from
`bundles.json` plus your own in the hive's data folder. `library()` returns all of it in one payload for the
editor, so the interface never reads the catalog itself.
"""
import json
import os
import re

import sfp_clusters
import sfp_stack as v1

core = v1.core
HERE = os.path.dirname(os.path.abspath(__file__))
PURPOSES_FILE = os.path.join(os.path.dirname(HERE), 'purposes.json')
BUNDLES_FILE = os.path.join(os.path.dirname(HERE), 'bundles.json')
MARGIN = 0.35   # how far another job must lead the cluster's default purpose to take over, when the skill's name says it
MARGIN_DESCRIPTION = 2.0   # ... and never when only its description does (scores are 0 to 1, so the default always stands)


def _read(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def rules():
    return _read(PURPOSES_FILE, {'purposes': [], 'phase_purpose': {}, 'name_rx': [], 'cluster_purpose': {}, 'names': {}})


def _phase_scores(name):
    sp = v1.SKILL_PHASE.get(name) or {}
    top = max(sp.values()) if sp else 0
    return {p: s / top for p, s in sp.items()} if top else {}


def purpose_of(skill, home_cluster, other_clusters=(), r=None):
    """(primary purpose id, [secondary ids], how) for one skill."""
    r = r or rules()
    name = skill['name']
    cp = r['cluster_purpose']
    secondary = []

    def cluster_default(cid):
        v = cp.get(cid)
        if v is None and cid.startswith('other-'):
            return 'build'
        return v['default'] if isinstance(v, dict) else v

    for cid in other_clusters:
        d = cluster_default(cid)
        if d:
            secondary.append(d)

    def others(primary):
        return [p for p in dict.fromkeys(secondary) if p != primary][:2]

    if name in r.get('names', {}):
        return r['names'][name], others(r['names'][name]), 'name'
    for pid, rx in r.get('name_rx', []):
        if re.search(rx, name):
            return pid, others(pid), 'name pattern'
    v = cp.get(home_cluster)
    if isinstance(v, dict) and v.get('by_phase'):
        scores = _phase_scores(name)
        if scores:
            ranked = sorted(scores, key=lambda p: (-scores[p], v1.PHASE_ORDER.index(p)))
            first = r['phase_purpose'][ranked[0]]
            # Words for a job turn up in every description ("error", "performance"). The cluster's default
            # stands unless another job leads it clearly.
            inv = {pu: ph for ph, pu in r['phase_purpose'].items()}
            lead = scores[ranked[0]] - scores.get(inv.get(v['default'], ''), 0.0)
            in_name = bool(set(core.tokens(name.replace('-', ' '))) & v1.PHASE_LEX[ranked[0]])
            if first != v['default'] and lead < (MARGIN if in_name else MARGIN_DESCRIPTION):
                first = v['default']
            if len(ranked) > 1 and scores[ranked[1]] >= 0.6:
                secondary.insert(0, r['phase_purpose'][ranked[1]])
            sec = [p for p in dict.fromkeys(secondary) if p != first]
            return first, sec[:2], 'job'
        return v['default'], [p for p in dict.fromkeys(secondary) if p != v['default']][:2], 'cluster default'
    primary = cluster_default(home_cluster) or 'build'
    return primary, [p for p in dict.fromkeys(secondary) if p != primary][:2], 'cluster'


def assignments(home=None):
    """{skill name: {purpose, also, how}} for every skill."""
    r = rules()
    home = home or sfp_clusters.assign()
    out = {}
    for s in core.CATALOG['skills']:
        ids = home[s['name']]
        p, also, how = purpose_of(s, ids[0], ids[1:], r)
        out[s['name']] = {'purpose': p, 'also': also, 'how': how}
    return out


# ------------------------------------------------------------------ bundles

def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'bundle'


def _user_bundles_path():
    return os.path.join(sfp_clusters._data_dir(), 'bundles.json')


def user_bundles():
    return _read(_user_bundles_path(), {'bundles': []})['bundles']


def _humanize(recipe_id):
    text = recipe_id.replace('-', ' ')
    return text[:1].upper() + text[1:]


def bundles():
    """Every bundle: the shared ones (some drawn from the hive's recipes), then yours."""
    recipes = {r['name']: r for r in v1.RECIPES}
    out = []
    for b in _read(BUNDLES_FILE, {'bundles': []})['bundles']:
        if 'recipe' in b:
            r = recipes.get(b['recipe'])
            if not r:
                continue   # the recipe was removed or names a skill that is gone
            out.append({'id': b['recipe'], 'name': _humanize(b['recipe']), 'goal': r['goal'][:1].upper() + r['goal'][1:] + '.',
                        'purpose': b.get('purpose', 'build'), 'when': b.get('when', ''), 'skills': list(r['skills']),
                        'mine': False, 'recipe': True})
        else:
            skills = [s for s in b['skills'] if s in core.SKILLS]
            out.append({'id': b['id'], 'name': b['name'], 'goal': b.get('goal', ''), 'purpose': b.get('purpose', 'build'),
                        'when': b.get('when', ''), 'skills': skills, 'mine': False, 'recipe': False})
    for b in user_bundles():
        skills = [s for s in b.get('skills', []) if s in core.SKILLS]
        out.append({'id': 'mine-' + _slug(b['name']), 'name': b['name'], 'goal': b.get('goal', ''), 'purpose': b.get('purpose', 'build'),
                    'when': b.get('when', ''), 'skills': skills, 'mine': True, 'recipe': False})
    for b in out:
        b['tokens'] = sum(v1.body_tokens(s) for s in b['skills'])
    return out


def find_bundle(ident):
    """A bundle by id or by exact name (case-insensitive)."""
    ident = (ident or '').strip().lower()
    for b in bundles():
        if b['id'].lower() == ident or b['name'].lower() == ident:
            return b
    return None


def add_user_bundle(name, skills, goal='', purpose='build', when=''):
    """Add or replace a bundle of your own. Unknown skills are refused with the closest matches."""
    resolved = []
    for n in skills:
        r = core.resolve_name(n)
        if not r:
            near = [x['name'] for x in core.search(n, limit=3)]
            raise SystemExit('no skill named %r.%s' % (n, (' Closest: %s.' % ', '.join(near)) if near else ''))
        resolved.append(r)
    if not resolved:
        raise SystemExit('a bundle needs at least one skill')
    if purpose not in {p['id'] for p in rules()['purposes']}:
        raise SystemExit('unknown purpose %r. Choose from: %s' % (purpose, ', '.join(p['id'] for p in rules()['purposes'])))
    data = _read(_user_bundles_path(), {'bundles': []})
    data['bundles'] = [b for b in data['bundles'] if b['name'] != name]
    data['bundles'].append({'name': name, 'goal': goal, 'purpose': purpose, 'when': when, 'skills': list(dict.fromkeys(resolved))})
    os.makedirs(sfp_clusters._data_dir(), exist_ok=True)
    with open(_user_bundles_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    return {'id': 'mine-' + _slug(name), 'name': name, 'skills': list(dict.fromkeys(resolved))}


def remove_user_bundle(name):
    data = _read(_user_bundles_path(), {'bundles': []})
    before = len(data['bundles'])
    data['bundles'] = [b for b in data['bundles'] if b['name'] != name and 'mine-' + _slug(b['name']) != name]
    if len(data['bundles']) != before:
        with open(_user_bundles_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1)
    return {'removed': before - len(data['bundles'])}


# ------------------------------------------------------------------ the payload for the editor

def library():
    """Everything the sidebar needs, in one object: purposes, clusters, bundles and every skill with its
    search terms. Usage comes from the hive's logs."""
    r = rules()
    home = sfp_clusters.assign()
    assigned = assignments(home)
    used = sfp_clusters.usage()
    cl = sfp_clusters.clusters(with_usage=True, used=used, home=home)
    docs = {s['name']: (name, desc) for s, name, desc, _cat in core.INDEX}
    skills = {}
    for s in core.CATALOG['skills']:
        n = s['name']
        a = assigned[n]
        name_terms, desc_terms = docs.get(n, (set(), {}))
        # the description words that say the most (rare across the catalog), so search can match them
        top = sorted(desc_terms, key=lambda w: (core.DF.get(w, 1), w))[:24]
        row = {'d': ' '.join(s['description'].split())[:180], 'category': s['category'], 'cluster': home[n][0],
               'purpose': a['purpose'], 'also': a['also'], 'n': sorted(name_terms), 't': top}
        if used.get(n):
            row['usage'] = used[n]
        if s.get('app'):
            row['app'] = s['app']
        skills[n] = row
    purposes = []
    for p in r['purposes']:
        members = [n for n, v in assigned.items() if v['purpose'] == p['id']]
        purposes.append(dict(p, count=len(members), used=sum(1 for m in members if used.get(m, {}).get('chosen'))))
    return {
        'version': 1,
        'counts': {'skills': len(skills), 'purposes': len(purposes), 'clusters': len(cl), 'bundles': len(bundles())},
        'purposes': purposes,
        'clusters': [{'id': c['id'], 'name': c['name'], 'description': c['description'], 'mine': c['mine'], 'count': c['count'],
                      'used': c.get('used', 0), 'skills': [s['name'] for s in c['skills']]} for c in cl],
        'bundles': bundles(),
        'skills': skills,
    }
