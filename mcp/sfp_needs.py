"""What a task needs that the model cannot do by itself.

Some tasks cannot be done by a model alone: it cannot make a 3D mesh, open a web page, draw a picture, see a page it
built, or carry on once its limit runs out. `capabilities.json` lists those abilities and what supplies each: skills, a
program (apps/apps.json) and sometimes a key. `needs()` reads the task and the project and returns the abilities it
needs, with the provider skills to attach and preload and, when asked, what is missing. `decide()` is the hive's
selection with that added: the first provider skill of every need joins the stack, the rest are preloaded.

Matching is regular expressions and a few project terms, so it costs well under a millisecond. Checking programs runs
their `--version`, so it is only done when asked (`check=True`), never on every keystroke.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
THRESHOLD = 0.5
PROJECT_BOOST = 0.3
_CAPS = None


def capabilities():
    global _CAPS
    if _CAPS is None:
        with open(os.path.join(ROOT, 'capabilities.json'), encoding='utf-8') as f:
            _CAPS = json.load(f)['capabilities']
        for c in _CAPS:
            c['_rx'] = [(re.compile(rx, re.I), w) for rx, w in c['triggers']]
    return _CAPS


def score(cap, task, project_terms=()):
    s = sum(w for rx, w in cap['_rx'] if rx.search(task or ''))
    if s and project_terms and set(cap.get('project', [])) & set(project_terms):
        s += PROJECT_BOOST
    elif not s and project_terms and set(cap.get('project', [])) & set(project_terms):
        return 0.0          # the project alone never makes a need: the task has to ask for it
    return min(s, 1.0)


def _app_state(app_id):
    sys.path.insert(0, os.path.join(ROOT, 'apps'))
    import sfp_app
    apps = sfp_app.load()
    if app_id not in apps:
        return None
    state, lines, ok, installed, running = sfp_app.status(apps[app_id])
    return {'id': app_id, 'name': apps[app_id]['name'], 'state': state, 'installed': installed, 'running': running,
            'requirements_met': ok, 'install': 'python3 apps/sfp_app.py install %s' % app_id,
            'start': 'python3 apps/sfp_app.py start %s' % app_id}


def needs(task, project_terms=(), check=False, exclude=()):
    """The abilities the task needs, strongest first. `check` adds the state of programs and keys."""
    out = []
    skip = set(exclude)
    for c in capabilities():
        s = score(c, task, project_terms)
        if s < THRESHOLD:
            continue
        skills = [n for n in c['skills'] if n not in skip]
        if not skills:
            continue
        item = {'id': c['id'], 'name': c['name'], 'why': c['why'], 'score': round(s, 2), 'skills': skills,
                'attach': skills[0], 'preload': skills[1:]}
        if check:
            item['apps'] = [a for a in (_app_state(i) for i in c['apps']) if a]
            item['env_missing'] = [v for v in c.get('env', []) if not os.environ.get(v)]
            item['action'] = _action(item)
        out.append(item)
    return sorted(out, key=lambda n: -n['score'])


def _action(item):
    """The one next step that unblocks this need, or 'ready'."""
    apps = item.get('apps') or []
    # Any one program of the group is enough, so only complain when none is installed.
    if apps and not any(a['installed'] for a in apps if a['installed'] is not None) and all(a['installed'] is False for a in apps):
        return 'install ' + apps[0]['id'] + ': ' + apps[0]['install']
    if any(a['installed'] and a['running'] is False for a in apps):
        a = next(a for a in apps if a['installed'] and a['running'] is False)
        return 'start ' + a['id'] + ': ' + a['start']
    if item.get('env_missing'):
        return 'set ' + ', '.join(item['env_missing']) + ' in your environment'
    return 'ready'


def decide(task, project=None, goal=None, after=(), budget=12000, max_skills=4, include=(), exclude=(), explain=False,
           check=False, learn=True):
    """sfp_learn.decide plus needs: provider skills join the stack, the rest are preloaded."""
    import sfp_hive as sel
    import sfp_learn
    terms = list(sel.scan(project).get('terms', {})) if project else []
    found = needs(task, terms, check=check, exclude=exclude)
    attach = [n['attach'] for n in found if n['attach'] not in include]
    inc = list(dict.fromkeys(list(include) + attach))
    res = sfp_learn.decide(task, project, goal, after, budget, max(max_skills, len(inc)), learn=learn, include=inc,
                           exclude=exclude, explain=explain)
    chosen = {c['name'] for c in res['stack']}
    res['needs'] = found
    res['preload'] = [{'name': p, 'why': 'next step of "%s"' % n['name']} for n in found for p in n['preload']
                      if p not in chosen]
    return res


def format_needs(found):
    if not found:
        return 'Nothing here needs more than the model itself.'
    lines = []
    for n in found:
        lines.append('%-34s %.2f  attach %s%s' % (n['name'], n['score'], n['attach'],
                                                 ('  then ' + ', '.join(n['preload'])) if n['preload'] else ''))
        lines.append('    ' + n['why'])
        if n.get('action'):
            lines.append('    ' + n['action'])
    return '\n'.join(lines)
