"""Group the skills into named clusters, and show which have been used.

`clusters.json` in the repository holds the shared clusters; clusters of your own (a name and a list of skills)
go in `clusters.json` in the hive's data folder. Usage comes from the hive's own logs: how often each skill was
chosen, and what feedback said about it.
"""
import json
import os
import re

import sfp_stack as v1

core = v1.core
HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(os.path.dirname(HERE), 'clusters.json')


def _data_dir():
    import sfp_learn
    return sfp_learn.data_dir()


def _user_path():
    return os.path.join(_data_dir(), 'clusters.json')


def _read(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def shared_rules():
    return _read(SHARED, {'clusters': []})['clusters']


def user_clusters():
    return _read(_user_path(), {'clusters': []})['clusters']


def _matches(rule, skill):
    if rule.get('categories') and skill['category'] not in rule['categories']:
        return False
    if rule.get('name_rx') and not re.search(rule['name_rx'], skill['name']):
        return False
    return bool(rule.get('categories') or rule.get('name_rx'))


def assign(skills=None, rules=None):
    """{skill name: [cluster ids]}, the first being its home cluster. Every skill gets a home."""
    skills = skills if skills is not None else core.CATALOG['skills']
    rules = rules if rules is not None else shared_rules()
    out = {}
    for s in skills:
        hits = [r['id'] for r in rules if _matches(r, s)]
        out[s['name']] = (hits or ['other-' + s['category']])[:3]
    return out


def usage():
    """{skill: {chosen, helped, unhelpful, ignored, missing}} from the hive's decision and feedback logs."""
    import sfp_learn
    counts = {}

    def bump(name, key):
        row = counts.setdefault(name, {'chosen': 0, 'helped': 0, 'unhelpful': 0, 'ignored': 0, 'missing': 0})
        row[key] += 1

    for row in sfp_learn._read_lines(sfp_learn._path('decisions.jsonl')):
        for name in row.get('stack', []):
            bump(name, 'chosen')
    for row in sfp_learn._read_lines(sfp_learn._path('feedback.jsonl')):
        if row.get('skill') and row.get('verdict') in ('helped', 'unhelpful', 'ignored', 'missing'):
            bump(row['skill'], row['verdict'])
    return counts


def clusters(with_usage=False):
    """The clusters, each with its skills, in the order of clusters.json, then yours."""
    rules = shared_rules()
    home = assign(rules=rules)
    used = usage() if with_usage else {}
    by_id = {r['id']: {'id': r['id'], 'name': r['name'], 'description': r.get('description', ''), 'mine': False, 'skills': []}
             for r in rules}
    for s in core.CATALOG['skills']:
        cid = home[s['name']][0]
        if cid not in by_id:
            by_id[cid] = {'id': cid, 'name': s['category'].replace('-', ' ').capitalize() + ', other', 'description': '',
                          'mine': False, 'skills': []}
        entry = {'name': s['name'], 'category': s['category'], 'also_in': home[s['name']][1:],
                 'description': ' '.join(s['description'].split())[:160]}
        if with_usage:
            entry['usage'] = used.get(s['name'], {})
        by_id[cid]['skills'].append(entry)
    out = [c for c in by_id.values() if c['skills']]
    known = {s['name']: s for s in core.CATALOG['skills']}
    for u in user_clusters():
        skills = []
        for n in u.get('skills', []):
            name = core.resolve_name(n)
            if name and name in known:
                e = {'name': name, 'category': known[name]['category'], 'also_in': home[name][:1],
                     'description': ' '.join(known[name]['description'].split())[:160]}
                if with_usage:
                    e['usage'] = used.get(name, {})
                skills.append(e)
        out.append({'id': 'mine-' + _slug(u['name']), 'name': u['name'], 'description': u.get('description', ''),
                    'mine': True, 'skills': skills})
    for c in out:
        c['count'] = len(c['skills'])
        if with_usage:
            c['used'] = sum(1 for s in c['skills'] if s['usage'].get('chosen'))
    return out


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'cluster'


def add_user_cluster(name, skills, description=''):
    """Add or replace a cluster of your own. Unknown skill names are refused with the closest matches."""
    resolved = []
    for n in skills:
        r = core.resolve_name(n)
        if not r:
            near = [x['name'] for x in core.search(n, limit=3)]
            raise SystemExit('no skill named %r.%s' % (n, (' Closest: %s.' % ', '.join(near)) if near else ''))
        resolved.append(r)
    data = _read(_user_path(), {'clusters': []})
    data['clusters'] = [c for c in data['clusters'] if c['name'] != name]
    data['clusters'].append({'name': name, 'description': description, 'skills': list(dict.fromkeys(resolved))})
    os.makedirs(_data_dir(), exist_ok=True)
    with open(_user_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    return {'name': name, 'skills': resolved}


def remove_user_cluster(name):
    data = _read(_user_path(), {'clusters': []})
    before = len(data['clusters'])
    data['clusters'] = [c for c in data['clusters'] if c['name'] != name]
    if len(data['clusters']) != before:
        with open(_user_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1)
    return {'removed': before - len(data['clusters'])}


def format_clusters(res):
    lines = []
    for c in res:
        used = (' (%d used)' % c['used']) if c.get('used') else ''
        lines.append('%-48s %4d%s%s' % (c['name'], c['count'], used, '  [yours]' if c['mine'] else ''))
    return '\n'.join(lines)
