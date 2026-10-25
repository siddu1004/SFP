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
import urllib.request

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


def router_state(port=8787):
    """Is SFP's own router set up, and is it running? (A local probe, about a millisecond when nothing listens.)"""
    import sfp_route
    cfg = sfp_route.load_config()
    models = sum(len(p.get('models', [])) for p in cfg.get('providers', []))
    running = False
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/health' % port, timeout=0.5):
            running = True
    except OSError:
        pass
    return {'configured': models > 0, 'models': models, 'running': running, 'port': port}


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
            if c.get('router'):
                item['router'] = router_state()
            item['apps'] = [a for a in (_app_state(i) for i in c['apps']) if a]
            item['env_missing'] = [v for v in c.get('env', []) if not os.environ.get(v)]
            item['action'] = _action(item)
        out.append(item)
    return sorted(out, key=lambda n: -n['score'])


def _action(item):
    """The one next step that unblocks this need, or 'ready'."""
    r = item.get('router')
    if r:
        if r['running']:
            return 'ready'
        if r['configured']:
            return 'start the router: python3 mcp/sfp_route.py serve'
        return 'set up the router: python3 mcp/sfp_route.py setup --yes && python3 mcp/sfp_route.py serve'
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


def plan_bundles(task, project=None, exclude=(), include=(), terms=None, preview=None):
    """The bundles that fit the task, judged on its words and on what the hive would choose by itself.
    A bundle fit well enough (score >= PUSH_MIN) is `push`: its skills all join the stack."""
    import sfp_hive as sel
    import sfp_library
    if preview is None:
        preview = [c['name'] for c in sel.select(task, project, max_skills=6, exclude=exclude)['stack']]
    return sfp_library.match_bundles(task, chosen=list(preview) + list(include), limit=2,
                                     exclude=())


def decide(task, project=None, goal=None, after=(), budget=12000, max_skills=4, include=(), exclude=(), explain=False,
           check=False, learn=True, bundles='push'):
    """sfp_learn.decide plus needs and bundles. Provider skills of every need join the stack, the rest are preloaded.
    `bundles`: 'push' attaches a bundle that fits the task well, whole and in order; 'suggest' only lists and preloads
    it; 'off' does neither."""
    import sfp_hive as sel
    import sfp_learn
    terms = list(sel.scan(project).get('terms', {})) if project else []
    found = needs(task, terms, check=check, exclude=exclude)
    attach = [n['attach'] for n in found if n['attach'] not in include]
    inc = list(dict.fromkeys(list(include) + attach))
    matches = []
    if bundles != 'off':
        matches = plan_bundles(task, project, exclude, inc)
        top = matches[0] if matches else None
        if bundles == 'push' and top and top['push'] and max_skills >= 3:
            inc = list(dict.fromkeys(inc + [n for n in top['skills'] if n not in set(exclude)]))
    res = sfp_learn.decide(task, project, goal, after, budget, max(max_skills, len(inc)), learn=learn, include=inc,
                           exclude=exclude, explain=explain)
    chosen = {c['name'] for c in res['stack']}
    res['needs'] = found
    res['preload'] = [{'name': p, 'why': 'next step of "%s"' % n['name']} for n in found for p in n['preload']
                      if p not in chosen]
    for m in matches:
        m['applied'] = all(n in chosen for n in m['skills'] if n not in set(exclude))
        m['missing'] = [n for n in m['skills'] if n not in chosen]
        if not m['applied']:
            res['preload'] += [{'name': n, 'why': 'rest of the "%s" bundle' % m['name']} for n in m['missing']
                               if n not in {p['name'] for p in res['preload']}]
    res['bundles'] = matches
    # Skills a need or a bundle brought in are not the user's pins: say where they came from.
    origin = {}
    if matches and matches[0].get('applied'):
        for n in matches[0]['skills']:
            origin.setdefault(n, 'part of the "%s" bundle' % matches[0]['name'])
    for n in found:
        origin.setdefault(n['attach'], 'needed to %s' % n['name'][0].lower() + n['name'][1:])
    for c in res['stack']:
        if c['name'] in origin and c['name'] not in set(include):
            c['reasons'] = [origin[c['name']] if r == 'pinned by you' else r for r in c.get('reasons', [])]
    iv = res.get('intervention')
    if iv is not None:
        # `pinned` and `excluded` are the user's own choices; what a need or a bundle added is reported under `needs` and `bundles`.
        if include or exclude:
            iv['pinned'] = [n for n in iv['pinned'] if n in set(include)]
        else:
            res.pop('intervention')
    if matches and matches[0]['applied']:
        res['bundle'] = {'id': matches[0]['id'], 'name': matches[0]['name']}
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
