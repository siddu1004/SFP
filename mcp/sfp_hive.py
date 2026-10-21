#!/usr/bin/env python3
"""SFP hive: a colony algorithm that decides which skills an agent uses, and when.

A honeybee colony has no manager. The queen lays eggs; she does not hand out
work. Yet thousands of bees split the work well, through three mechanisms that
biologists have measured and modelled. This engine copies them.

1. Scouts, waggle dances and quorum (nest-site selection, Seeley 2010).
   Independent scouts each judge the options. A scout dances for an option in
   proportion to its quality, which recruits more bees to it. Scouts for rival
   options head-butt each other's dancers with stop signals. The colony commits
   once an option has a quorum.
     Here the scouts are independent signals: the task's words, the project's
     technologies, the phase of work, the task's category, and the trail left
     by the last skill used. Support for each skill grows by recruitment and is
     cut by stop signals from rival skills that would do the same job
     (cross-inhibition, Seeley et al. 2012; Pais et al. 2013). A skill is chosen
     only with a quorum: the task's words alone must be strong, or at least two
     independent scouts must back it. One noisy signal cannot decide.

2. Response thresholds (division of labour, Bonabeau, Theraulaz and Deneubourg 1996).
   Each bee has a threshold for each job. The need for a job is a stimulus; a
   bee takes it up with probability s^2 / (s^2 + theta^2). Doing the job lowers
   the stimulus, so the next bee is less likely to join. Doing a job well lowers
   a bee's threshold for it (specialisation); failing raises it.
     Here the jobs are phases of work (plan, build, test, secure, ship ...).
     The task sets the stimulus for each. Each chosen skill takes the job it
     responds to most, if its response clears the engagement level, and the
     stimulus for that job drops. So a task gets the few skills it needs, one or
     two per job, and a job nobody asked for gets none. Recorded outcomes move
     each skill's threshold.

3. Stigmergy (ant pheromone trails, Dorigo's ant colony optimisation).
   Ants that find a good path leave pheromone; others follow strong trails;
   pheromone evaporates, so stale paths fade.
     Here each recorded move from one skill to the next lays pheromone on that
     edge, with a half-life of 30 days. The recipes are permanent trails. The
     next-skill prediction follows the trails, smoothed by what usually follows
     a skill's category and phase (a Markov chain with evaporation).

It runs inside the caller's process (the MCP server or the skill's script) in
tens of milliseconds, so there is no extra service to wait on. Standard library
only; nothing leaves the machine.

CLI
  sfp_hive.py recommend "write tests for the order view" --project .
  sfp_hive.py next api-design
  sfp_hive.py record api-design --outcome helped
  sfp_hive.py evaluate
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import sfp_mcp as core  # noqa: E402
import sfp_stack as v1  # noqa: E402  (vocabulary, project fingerprint, recipes, usage log)

VERSION = '2.0.0'

# Languages, as opposed to frameworks. A project that shows only a language
# (a Package.swift, a go.mod) may use any framework of it.
LANGS = {v1._one(t) for t in ('python javascript typescript nodejs golang rust java kotlin swift dart php ruby '
                              'csharp fsharp cpp perl solidity arkts').split()}
IMPLIES = {v1._one(k): {v1._one(x) for x in vs} for k, vs in v1.IMPLIES.items()}

# The colony's constants, named after the biology so the code reads like the model.
SCOUT_FLOOR = 0.3        # a scout backs a skill when its vote is at least this
STRONG_WORDS = 0.8       # the task's words alone are a quorum when this strong
STOP_SIGNAL = 0.5        # how much a chosen skill inhibits a rival, per unit of rivalry
STOP_SAME_JOB = 0.5      # extra rivalry between skills for the same job in the same field
THETA = 0.5              # base response threshold
ENGAGE = 0.20            # response a skill needs to take up a job
BASE_DEMAND = 0.50       # every job has some need, so a strong specialist can join one the task did not name
WORK_DONE = 0.6          # how much of a job's stimulus one engaged skill uses up
LEARN, FORGET = 0.15, 0.15   # threshold change per helped / unhelpful outcome
HALF_LIFE_DAYS = 30.0    # pheromone evaporation


# ---------------------------------------------------------------- the scouts

def relation(tech, ctx_tech):
    """How a skill's technologies relate to the project's: fit, near, general, unasked or mismatch."""
    if not tech:
        return 'general'
    if not ctx_tech:
        return 'unasked'
    if tech & ctx_tech:
        return 'fit'
    # A framework skill in a project that only shows its language: plausible, not wrong.
    if not (ctx_tech - LANGS) and any(IMPLIES.get(t, set()) & ctx_tech for t in tech):
        return 'near'
    return 'mismatch'


def read_situation(task, goal, scan_result):
    text = ' '.join(x for x in (task or '', goal or '') if x)
    words = v1.task_words(text)
    ctx = dict(scan_result['terms'])
    for w in words:
        if w in v1.TECH_STEMS:
            ctx[w] = max(ctx.get(w, 0), 4.0)
            for imp in IMPLIES.get(w, ()):
                ctx[imp] = max(ctx.get(imp, 0), 2.4)
    ctx_tech = {t for t in ctx if t in v1.TECH_STEMS}
    demand = dict(v1.phase_of_text(goal or '') or v1.phase_of_text(task or ''))
    if goal and task:
        for p, v in v1.phase_of_text(task).items():
            demand[p] = demand.get(p, 0) * 0.7 + v * 0.3
    said = {}
    for raw in core.raw_words(text):
        for s in core.tokens(raw):
            said.setdefault(v1.SYNONYMS.get(s, s), raw)
    return {'text': text, 'words': words, 'ctx': ctx, 'ctx_tech': ctx_tech, 'demand': demand, 'said': said}


def send_scouts(sit, after, trails):
    """Every scout votes on every candidate it knows about. Votes are 0..1; None means the scout abstains."""
    words, ctx, ctx_tech = sit['words'], sit['ctx'], sit['ctx_tech']
    found = {}
    if words:
        query = ' '.join(words)
        for score, s in core.scored_search(query, limit=150):
            found[s['name']] = max(found.get(s['name'], 0), score)
        if ctx_tech:
            lead = sorted(ctx_tech, key=lambda t: (-ctx[t], t))[:3]
            for score, s in core.scored_search(query + ' ' + ' '.join(lead), limit=80):
                found[s['name']] = max(found.get(s['name'], 0), 0.8 * score)
    top = max(found.values()) if found else 1.0
    trail = {}
    if after:
        trail = {b: p for p, b in trails.next(after[-1], limit=15, exclude=after)}
    top_trail = max(trail.values()) if trail else 1.0
    cat_fit = v1.category_fit(words)
    top_ctx = max(ctx.values()) if ctx else 1.0

    votes = {}
    for name in set(found) | set(trail):
        if name in after or name in ('sfp', 'sfp-manager'):
            continue
        tech = v1.SKILL_TECH.get(name, set())
        rel = relation(tech, ctx_tech)
        if rel == 'fit':
            project = max(ctx[t] for t in tech & ctx_tech) / top_ctx
        elif rel == 'near':
            project = 0.4
        elif rel in ('mismatch', 'unasked'):
            project = 0.0
        else:
            project = None  # a general skill: the project scout has no opinion
        phase = None
        if sit['demand'] and v1.SKILL_PHASE.get(name):
            phase = v1.cosine(sit['demand'], v1.SKILL_PHASE[name])
        votes[name] = {
            'words': found.get(name, 0) / top,
            'project': project,
            'role': phase,
            'category': cat_fit.get(core.SKILLS[name]['category']),
            'trail': trail[name] / top_trail if name in trail else None,
            'relation': rel,
        }
    return votes


def nectar(v):
    """An option's quality: the task's words, scaled up or down by every other scout (v1's scoring, proven on the benchmark)."""
    q = v['words']
    q *= 1 + 0.3 * (v['category'] or 0)
    if v['role'] is not None:
        q *= 0.85 + 0.3 * v['role']
    q *= 1 + 0.5 * (v['project'] if v['project'] is not None else 0.6)
    if v['relation'] == 'mismatch':
        q *= 0.4
    elif v['relation'] == 'unasked':
        q *= 0.8
    q *= 1 + 0.3 * (v['trail'] or 0)
    return q


def support(v):
    """The independent scouts that back an option."""
    return [k for k in ('words', 'project', 'role', 'category', 'trail') if (v[k] or 0) >= SCOUT_FLOOR]


def has_quorum(v):
    if not v['words'] or v['relation'] == 'mismatch':
        return False  # the task must name what the skill is for, and it must suit the project
    return v['words'] >= STRONG_WORDS or len(support(v)) >= 2


# ------------------------------------------------- stop signals and labour

def rivalry(a, b):
    """How hard two skills compete. Near-identical skills fight hard; skills that share a job
    but do different parts of it (unit tests and end-to-end tests) barely do."""
    sim = v1.similarity(a, b)
    same_job = core.SKILLS[a]['category'] == core.SKILLS[b]['category'] and v1.main_phase(a) == v1.main_phase(b)
    return sim + (STOP_SAME_JOB if same_job else 0.0)


def affinity(name):
    vec = v1.SKILL_PHASE.get(name) or {v1.main_phase(name): 1.0}
    top = max(vec.values())
    return {p: vec.get(p, 0) / top for p in v1.PHASE_ORDER}


def respond(stimulus, theta):
    """Bonabeau's response function: the chance a bee takes up a job of stimulus s, with threshold theta."""
    return stimulus * stimulus / (stimulus * stimulus + theta * theta) if stimulus > 0 else 0.0


def forage(quality, demand, col, budget, max_skills):
    """Choose the stack: stop signals between rivals, then response thresholds for each job.

    Repeatedly take the option with the most quality left after the stop signals of the skills
    already chosen (each chosen skill inhibits a rival by STOP_SIGNAL x rivalry). The option then
    looks at every job and responds to the one whose need, as it perceives it (the job's stimulus
    times the option's own quality), most exceeds its threshold for that job. If no response clears
    ENGAGE it stays in reserve. Taking a job uses up WORK_DONE of that job's stimulus, so a second
    skill joins the same job only if it is strong, and a third rarely does. The best option always
    goes out, so a task that has any fitting skill gets one.
    """
    stimulus = {p: BASE_DEMAND + (1 - BASE_DEMAND) * demand.get(p, 0.0) for p in v1.PHASE_ORDER}
    pool = dict(quality)
    chosen, reserve, spent = [], [], 0
    while pool and len(chosen) < max_skills:
        # Experienced foragers respond first: a lowered threshold raises the quality a skill perceives.
        left = {n: q / col.threshold_scale(n) - STOP_SIGNAL * max((rivalry(n, c[0]) for c in chosen), default=0.0)
                for n, q in pool.items()}
        name = max(left, key=lambda n: (left[n], n))
        pool.pop(name)
        if left[name] <= 0:
            break  # everything left is suppressed by a rival already chosen
        aff = affinity(name)
        scale = col.threshold_scale(name)
        best_p, best_r = None, -1.0
        for p in v1.PHASE_ORDER:
            r = respond(stimulus[p] * left[name], THETA * scale / (0.2 + 0.8 * aff[p]))
            if r > best_r:
                best_p, best_r = p, r
        cost = v1.body_tokens(name)
        if chosen and (best_r < ENGAGE or spent + cost > budget):
            reserve.append(name)
            continue
        chosen.append((name, best_p, best_r))
        spent += cost
        stimulus[best_p] *= 1 - WORK_DONE * best_r
    reserve += sorted(pool, key=lambda n: -pool[n])[:5]
    return chosen, reserve, spent, stimulus


# --------------------------------------------------------- pheromone trails

class Colony(v1.Markov):
    """The colony's memory: pheromone trails between skills and each skill's learned thresholds.

    Trails are the v1 Markov chain with evaporation: a move recorded `age` days ago
    lays exp(-age * ln 2 / HALF_LIFE_DAYS) of pheromone. Recipes are permanent trails.
    """

    def __init__(self, recipes=(), events=(), now=None):
        events = list(events)
        super().__init__(recipes, [])
        now = now or time.time()
        for seq, t in self._sessions(events):
            w = math.exp(-max(0.0, now - t) / 86400.0 * math.log(2) / HALF_LIFE_DAYS)
            for a, b in zip(seq, seq[1:]):
                if a == b:
                    continue
                self.c.setdefault(a, {})
                self.c[a][b] = self.c[a].get(b, 0) + w
                self.total[a] = self.total.get(a, 0) + w
                ca, cb = core.SKILLS[a]['category'], core.SKILLS[b]['category']
                self.cat_c.setdefault(ca, {})
                self.cat_c[ca][cb] = self.cat_c[ca].get(cb, 0) + w
                self.cat_total[ca] = self.cat_total.get(ca, 0) + w
        for e in events:
            if e.get('outcome') in ('helped', 'unhelpful'):
                h, u = self.outcome.get(e['skill'], (0, 0))
                self.outcome[e['skill']] = (h + (e['outcome'] == 'helped'), u + (e['outcome'] == 'unhelpful'))

    @staticmethod
    def _sessions(events, gap=2 * 3600):
        by_id, loose = {}, []
        for e in sorted(events, key=lambda e: e.get('t', 0)):
            (by_id.setdefault(e['session'], []) if e.get('session') else loose).append(e)
        groups, cur = [], []
        for e in loose:
            if cur and e.get('t', 0) - cur[-1].get('t', 0) > gap:
                groups.append(cur)
                cur = []
            cur.append(e)
        if cur:
            groups.append(cur)
        groups += list(by_id.values())
        return [([e['skill'] for e in g], g[-1].get('t', 0)) for g in groups]

    def threshold_scale(self, name):
        """Experience: each helped outcome lowers the threshold, each unhelpful one raises it."""
        h, u = self.outcome.get(name, (0, 0))
        return min(2.0, max(0.5, (1 - LEARN) ** h * (1 + FORGET) ** u))


def colony():
    return Colony(v1.RECIPES, v1.read_usage())


# ----------------------------------------------------------------- the hive

_SCANS = {}


def scan(project):
    """The project fingerprint, cached for 30 seconds so a busy session does not rescan on every call."""
    if not project:
        return {'terms': {}, 'signals': [], 'files': 0}
    key = os.path.abspath(project)
    hit = _SCANS.get(key)
    if hit and time.time() - hit[0] < 30:
        return hit[1]
    res = v1.scan_project(key)
    _SCANS[key] = (time.time(), res)
    return res


def recommend(task, project=None, goal=None, after=(), budget=12000, max_skills=4, chain=None, scan_result=None):
    """Decide which skills to use for a task, in what order. Same result shape as sfp_stack.recommend, plus `colony`."""
    t0 = time.time()
    after = [n for n in (core.resolve_name(a) for a in (after or [])) if n]
    col = chain if chain is not None else colony()
    sc = scan_result if scan_result is not None else scan(project)
    sit = read_situation(task, goal, sc)

    votes = send_scouts(sit, after, col)
    quality = {n: nectar(v) for n, v in votes.items() if has_quorum(v)}
    if quality:
        top_q = max(quality.values())
        quality = {n: q / top_q for n, q in quality.items()}
    chosen, reserve, spent, left = forage(quality, sit['demand'], col, budget, max_skills)

    stack = []
    for name, phase, resp in chosen:
        v = votes[name]
        reasons = []
        hit = sorted(set(sit['words']) & v1.SKILL_TOKENS.get(name, set()))
        if hit:
            reasons.append('task words: ' + ', '.join(sit['said'].get(w, w) for w in hit[:4]))
        tech = v1.SKILL_TECH.get(name, set())
        if v['relation'] == 'fit':
            reasons.append('fits project: ' + ', '.join(v1.show(sorted(tech & sit['ctx_tech'])[:3])))
        elif v['relation'] == 'near':
            reasons.append('suits the project language')
        if v['trail']:
            reasons.append('trail from ' + after[-1])
        reasons.append('backed by: ' + ', '.join(support(v)))
        stack.append({'name': name, 'phase': phase, 'layer': v1.LAYER[phase], 'category': core.SKILLS[name]['category'],
                      'tokens': v1.body_tokens(name), 'score': round(quality[name], 3), 'support': len(support(v)),
                      'response': round(resp, 3), 'relevance': round(v['words'], 3),
                      'path': core.SKILLS[name]['path'] + '/SKILL.md', 'reasons': reasons})
    stack.sort(key=lambda c: (v1.PHASE_ORDER.index(c['phase']), -c['score']))

    used = {c['name'] for c in stack}
    recipe, best = None, 0.0
    for rc in v1.RECIPES:
        overlap = len(used & set(rc['skills'])) / max(1, min(len(used), len(rc['skills'])))
        gw = set(core.tokens(rc['goal']))
        val = max(overlap, len(set(sit['words']) & gw) / max(1, len(gw)))
        if val > best and val >= 0.5:
            recipe, best = rc, val
    nxt = []
    if stack:
        last = stack[-1]['name']
        for p, b in col.next(last, limit=40, exclude=used | set(after)):
            if relation(v1.SKILL_TECH.get(b, set()), sit['ctx_tech']) != 'mismatch':
                nxt.append({'name': b, 'probability': round(p, 4)})
            if len(nxt) == 3:
                break

    ctx = sit['ctx']
    return {
        'engine': 'hive ' + VERSION,
        'task': task, 'goal': goal,
        'project': {'technologies': v1.show(sorted(sit['ctx_tech'], key=lambda t: (-ctx[t], t))[:8]),
                    'evidence': sc['signals'][:8], 'files_scanned': sc['files']},
        'phases': {p: round(v, 2) for p, v in sorted(sit['demand'].items(), key=lambda kv: -kv[1])},
        'stack': stack,
        'tokens': spent,
        'recipe': recipe and {'name': recipe['name'], 'skills': recipe['skills']},
        'next': nxt,
        'colony': {'scouted': len(votes), 'quorum': len(quality),
                   'reserve': reserve[:5],
                   # jobs the task asked for that no skill took up in earnest
                   'unmet_demand': {p: round(sit['demand'][p], 2) for p in sit['demand']
                                    if sit['demand'][p] >= 0.25 and left[p] >= 0.75 * (BASE_DEMAND + (1 - BASE_DEMAND) * sit['demand'][p])}},
        'considered': len(votes),
        'ms': int((time.time() - t0) * 1000),
    }


# ---------------------------------------------------------------- evaluation

def _load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _projects(data, tmp):
    for proj, files in data['projects'].items():
        for rel, body in files.items():
            f = os.path.join(tmp, proj, rel)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            with open(f, 'w', encoding='utf-8') as fh:
                fh.write(body)


SETS = (('bench', None), ('proj', 'stack_eval.json'), ('fresh', 'hive_fresh.json'))


def evaluate(tests_dir=None, only=None):
    """Score the hive, the v1 engine and plain search on the task sets. Used by the tests and the README."""
    import tempfile
    tests_dir = tests_dir or os.path.join(os.path.dirname(HERE), 'tests')
    col = Colony(v1.RECIPES, [])  # recipes only, so personal usage never changes the published figures
    old = v1.Markov(v1.RECIPES, [])
    engines = {'hive': lambda t, p: recommend(t, p, chain=col), 'v1': lambda t, p: v1.recommend(t, p, chain=old)}
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for key, fname in SETS:
            if only and key not in only:
                continue
            if fname is None:
                cases = []
                for name in ('search_eval.json', 'search_holdout.json', 'search_fresh.json'):
                    path = os.path.join(tests_dir, name)
                    if os.path.isfile(path):
                        cases += [dict(c, project=None) for c in _load(path)]
            else:
                path = os.path.join(tests_dir, fname)
                if not os.path.isfile(path):
                    continue
                data = _load(path)
                _projects(data, os.path.join(tmp, key))
                cases = [dict(c, project=os.path.join(tmp, key, c['project'])) for c in data['cases']]
            n = len(cases)
            if not n:
                continue
            for eng, fn in engines.items():
                hit = first = wrong = size = tokens = ms = 0
                for c in cases:
                    want = {x for x in c['expect'] if x in core.SKILLS}
                    res = fn(c['task'], c['project'])
                    names = [x['name'] for x in res['stack']]
                    hit += bool(want & set(names))
                    if names:
                        lead = max(res['stack'], key=lambda x: x['score'])['name']
                        first += lead in want
                    wrong += bool(set(c.get('avoid', [])) & set(names))
                    size += len(names)
                    tokens += res['tokens']
                    ms += res['ms']
                out['%s_%s' % (key, eng)] = {'n': n, 'hit': hit / n, 'first': first / n, 'wrong': wrong,
                                              'size': size / n, 'tokens': tokens / n, 'ms': ms / n}
            k = max(1, round(out['%s_hive' % key]['size']))
            s_hit = s_wrong = 0
            for c in cases:
                top = {s['name'] for s in core.search(c['task'], limit=k)}
                s_hit += bool({x for x in c['expect'] if x in core.SKILLS} & top)
                s_wrong += bool(set(c.get('avoid', [])) & top)
            out['%s_search' % key] = {'n': n, 'hit': s_hit / n, 'wrong': s_wrong, 'size': k}
    return out


# ----------------------------------------------------------------------- CLI

def format_stack(res):
    lines = v1.format_stack(res).split('\n')
    col = res.get('colony') or {}
    if col:
        lines.insert(-1, 'Colony: %d skills scouted, %d reached quorum, %d took a job.' % (
            col['scouted'], col['quorum'], len(res['stack'])))
        if col.get('unmet_demand'):
            lines.insert(-1, 'No skill took up: %s' % ', '.join(col['unmet_demand']))
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='The SFP hive: decide which skills a task needs, and in what order.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('recommend', help='build a skill stack for a task')
    r.add_argument('task')
    r.add_argument('--project')
    r.add_argument('--goal')
    r.add_argument('--after', default='')
    r.add_argument('--budget', type=int, default=12000)
    r.add_argument('--max', type=int, default=4)
    r.add_argument('--engine', choices=['hive', 'v1'], default='hive', help='v1 is the previous weighted-score engine')
    r.add_argument('--json', action='store_true')
    n = sub.add_parser('next', help='follow the pheromone trails from one skill')
    n.add_argument('skill')
    n.add_argument('--limit', type=int, default=5)
    rec = sub.add_parser('record', help='record that a skill was used (local file only)')
    rec.add_argument('skill')
    rec.add_argument('--outcome', choices=['helped', 'unhelpful'])
    rec.add_argument('--session')
    p = sub.add_parser('profile', help='show what the scouts detect in a project')
    p.add_argument('path', nargs='?', default='.')
    sub.add_parser('recipes', help='list the permanent trails (named stacks)')
    sub.add_parser('evaluate', help='score the hive against v1 and plain search')
    a = ap.parse_args(argv)

    if a.cmd == 'recommend':
        after = [x for x in a.after.split(',') if x.strip()]
        if a.engine == 'v1':
            res = v1.recommend(a.task, a.project, a.goal, after, a.budget, a.max)
            print(json.dumps(res, indent=1) if a.json else v1.format_stack(res))
        else:
            res = recommend(a.task, a.project, a.goal, after, a.budget, a.max)
            print(json.dumps(res, indent=1) if a.json else format_stack(res))
    elif a.cmd == 'next':
        name = core.resolve_name(a.skill)
        if not name:
            raise SystemExit('no skill named %r' % a.skill)
        for pr, b in colony().next(name, a.limit):
            print('%-40s %.3f' % (b, pr))
    elif a.cmd == 'record':
        print(json.dumps(v1.record(a.skill, a.outcome, a.session)))
    elif a.cmd in ('profile', 'recipes'):
        v1.main([a.cmd] + ([a.path] if a.cmd == 'profile' else []))
    elif a.cmd == 'evaluate':
        print(json.dumps({k: {m: round(x, 3) if isinstance(x, float) else x for m, x in v.items()}
                          for k, v in evaluate().items()}, indent=1))


if __name__ == '__main__':
    main()
