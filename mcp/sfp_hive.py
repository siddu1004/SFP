#!/usr/bin/env python3
"""SFP skill selection: choose the few skills a task needs, and the order to use them in.

Loading every skill is slow and noisy, and choosing by keyword alone ignores the project. This engine
combines five independent signals, requires them to agree, removes overlap, and assigns each chosen
skill a job. Then it learns from feedback (see sfp_learn.py).

Signals (each votes 0 to 1 on every candidate skill, or abstains)
  words      how well the task's words match the skill (the library's search)
  project    whether the skill's technology is in the project (read from its files)
  role       how well the skill's jobs match the phase of work the task asks for
  category   how much the task's words point at the skill's category
  history    how often this skill follows the skill used just before (a time-decayed Markov chain)

Selection
  1. Agreement. A skill is considered only if the task's words are strong, or two independent signals
     back it, and it is not for another technology than the project's.
  2. Quality. The task's words, scaled up or down by the other signals, then by what feedback has
     taught the model (sfp_learn.Model: which words go with which skills). With no feedback the
     scale is exactly 1.
  3. Overlap suppression. Skills are taken best first; each one lowers the quality of similar skills,
     so near-duplicates do not both appear.
  4. Role allocation. Every job (plan, build, test, secure, ship ...) has a level of need set by the
     task. A skill takes the job it suits best if its response s^2 / (s^2 + theta^2) clears a floor,
     and taking a job uses up part of its need, so a job gets one or two skills and an unneeded job
     gets none. The best skill is always taken.
  5. The stack is ordered by phase of work: base (does the work), check (verifies it), finish (ships it).

Background. Agreement and overlap suppression follow models of collective decision making in honeybee
nest-site selection (Seeley et al., Science 2012). Role allocation is the response-threshold model of
division of labour in social insects (Bonabeau, Theraulaz and Deneubourg, 1996). The history signal
is a Markov chain whose counts decay exponentially, in the way pheromone trails evaporate in ant
colony optimisation (Dorigo, 1992). The constants below were set on the benchmark in tests/; see
docs/HIVE.md for how, and for where it fails.

Runs inside the caller's process (the MCP server or the skill's script) in a few milliseconds. Python
standard library only; nothing leaves the machine.

CLI
  sfp_hive.py select "write tests for the order view" --project .
  sfp_hive.py feedback <decision> --helped django-tdd --unhelpful django-celery --missing python-testing
  sfp_hive.py status
  sfp_hive.py next api-design
  sfp_hive.py evaluate
"""
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

VERSION = '3.11.0'
INTERNAL_SKILLS = ('sfp', 'sfp-hive')   # the router and the hive never recommend themselves

# Languages, as opposed to frameworks. A project that shows only a language
# (a Package.swift, a go.mod) may use any framework of it.
LANGS = {v1._one(t) for t in ('python javascript typescript nodejs golang rust java kotlin swift dart php ruby '
                              'csharp fsharp cpp perl solidity arkts').split()}
# Tools that sit beside any language: a skill about only these does not conflict with the project's language.
TOOLS = {v1._one(t) for t in 'docker kubernetes terraform'.split()}
IMPLIES = {v1._one(k): {v1._one(x) for x in vs} for k, vs in v1.IMPLIES.items()}

SIGNALS = ('words', 'project', 'role', 'category', 'history')

BACKING = 0.3            # a signal backs a skill when its vote is at least this
NAMED = 0.97             # a skill whose words score this close to the best match is named by the task, whatever the project
STRONG_WORDS = 0.8       # the task's words alone are enough when this strong
OVERLAP_PENALTY = 0.5    # how much a chosen skill lowers a similar skill's quality, per unit of overlap
SAME_JOB_OVERLAP = 0.5   # extra overlap between skills for the same job in the same category
THETA = 0.5              # base response threshold of the role allocation
ENGAGE = 0.20            # response a skill needs to take a job
BASE_DEMAND = 0.50       # every job has some need, so a strong specialist can join one the task did not name
WORK_DONE = 0.6          # how much of a job's need one skill uses up
HALF_LIFE_DAYS = 30.0    # how fast recorded sequences fade from the history signal
RESCUE = 0.7             # learned preference strong enough to admit a skill that lacks agreement
RECALL = 0.3             # learned association strong enough to bring in a skill the search did not find


# ------------------------------------------------------------------ signals

def relation(tech, ctx_tech):
    """How a skill's technologies relate to the project's: fit, near, general, unasked or mismatch."""
    if not tech:
        return 'general'
    if not ctx_tech:
        return 'unasked'
    if tech & ctx_tech:
        return 'fit'
    if tech <= TOOLS:
        return 'near'   # a Docker skill suits a Python project as well as a Node one
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


def collect_signals(sit, after, history, recalled=None, phase_queries=()):
    """Every signal votes on every candidate it knows about. Votes are 0..1; None means the signal abstains."""
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
    for extra, weight in phase_queries:
        # The observed phase of work, as words: skills for that job can join even if the task did not name it.
        for score, s in core.scored_search(' '.join(words) + ' ' + extra, limit=60):
            if relation(v1.SKILL_TECH.get(s['name'], set()), ctx_tech) != 'mismatch':
                found[s['name']] = max(found.get(s['name'], 0), weight * score)
    top = max(found.values()) if found else 1.0
    for skill, z in (recalled or {}).items():
        # A skill that feedback has tied to this task's words, even if the search did not find it.
        if skill in core.SKILLS:
            found[skill] = max(found.get(skill, 0), top * min(0.9, 0.4 + 0.5 * z))
    follows = {}
    if after:
        follows = {b: p for p, b in history.next(after[-1], limit=15, exclude=after)}
    top_follow = max(follows.values()) if follows else 1.0
    cat_fit = v1.category_fit(words)
    top_ctx = max(ctx.values()) if ctx else 1.0

    votes = {}
    for name in set(found) | set(follows):
        if name in after or name in INTERNAL_SKILLS:
            continue
        tech = v1.SKILL_TECH.get(name, set())
        rel = relation(tech, ctx_tech)
        if rel == 'mismatch' and found.get(name, 0) >= NAMED * top:
            rel = 'named'   # the project cannot veto what the task asks for by name (a 3D skill in a web project)
        if rel == 'fit':
            project = max(ctx[t] for t in tech & ctx_tech) / top_ctx
        elif rel == 'near':
            project = 0.4
        elif rel in ('mismatch', 'unasked'):
            project = 0.0
        else:
            project = None  # a general skill: the project signal has no opinion
        role = None
        if sit['demand'] and v1.SKILL_PHASE.get(name):
            role = v1.cosine(sit['demand'], v1.SKILL_PHASE[name])
        votes[name] = {
            'words': found.get(name, 0) / top,
            'project': project,
            'role': role,
            'category': cat_fit.get(core.SKILLS[name]['category']),
            'history': follows[name] / top_follow if name in follows else None,
            'relation': rel,
        }
    return votes


def base_quality(v):
    """A candidate's quality before learning: the task's words, scaled by the other signals."""
    q = v['words']
    q *= 1 + 0.3 * (v['category'] or 0)
    if v['role'] is not None:
        q *= 0.85 + 0.3 * v['role']
    q *= 1 + 0.5 * (v['project'] if v['project'] is not None else 0.6)
    if v['relation'] == 'mismatch':
        q *= 0.4
    elif v['relation'] == 'unasked':
        q *= 0.8
    q *= 1 + 0.3 * (v['history'] or 0)
    return q


def backers(v):
    """The independent signals that back a candidate."""
    return [k for k in SIGNALS if (v[k] or 0) >= BACKING]


def has_agreement(v):
    if not v['words'] or v['relation'] == 'mismatch':
        return False  # the task must name what the skill is for, and it must suit the project
    return v['words'] >= STRONG_WORDS or len(backers(v)) >= 2


# ------------------------------------------------- overlap and role allocation

def overlap(a, b):
    """How much two skills overlap. Near-identical skills overlap a lot; skills that share a job
    but do different parts of it (unit tests and end-to-end tests) barely do."""
    sim = v1.similarity(a, b)
    same_job = core.SKILLS[a]['category'] == core.SKILLS[b]['category'] and v1.main_phase(a) == v1.main_phase(b)
    return sim + (SAME_JOB_OVERLAP if same_job else 0.0)


def affinity(name):
    vec = v1.SKILL_PHASE.get(name) or {v1.main_phase(name): 1.0}
    top = max(vec.values())
    return {p: vec.get(p, 0) / top for p in v1.PHASE_ORDER}


def respond(need, theta):
    """The response-threshold function: the share of a job's need a skill with threshold theta takes up."""
    return need * need / (need * need + theta * theta) if need > 0 else 0.0


def assemble(quality, demand, budget, max_skills, why=None):
    """Choose the stack: overlap suppression, then role allocation.

    Take the skill with the most quality left after the penalty for overlap with those already chosen.
    For subsequent choices, balance quality with response to unfulfilled layer demand so the stack covers
    base, check and finish layers when the task needs them.
    It then looks at every job and responds to the one whose need, scaled by the skill's own quality,
    most exceeds its threshold for that job. If no response clears ENGAGE (or the token budget would
    be broken) it stays in reserve. Taking a job uses up WORK_DONE of its need, so a second skill
    joins the same job only if it is strong. The best skill is always taken.
    `why`, when given, is filled with the reason each skill that was looked at was not taken.
    """
    why = why if why is not None else {}
    need = {p: BASE_DEMAND + (1 - BASE_DEMAND) * demand.get(p, 0.0) for p in v1.PHASE_ORDER}
    pool = dict(quality)
    chosen, reserve, spent = [], [], 0
    while pool and len(chosen) < max_skills:
        left = {n: q - OVERLAP_PENALTY * max((overlap(n, c[0]) for c in chosen), default=0.0) for n, q in pool.items()}
        if not chosen:
            name = max(left, key=lambda n: (left[n], n))
        else:
            def cand_key(n):
                aff = affinity(n)
                cur_need = max(need[p] * aff[p] for p in v1.PHASE_ORDER)
                return (left[n] * (1.0 + 0.35 * cur_need), left[n])
            name = max(left, key=cand_key)
        pool.pop(name)
        if left[name] <= 0:
            why[name] = 'overlaps a chosen skill'
            for n in pool:
                why.setdefault(n, 'overlaps a chosen skill')
            break  # everything left overlaps a skill already chosen
        aff = affinity(name)
        best_p, best_r = None, -1.0
        for p in v1.PHASE_ORDER:
            r = respond(need[p] * left[name], THETA / (0.2 + 0.8 * aff[p]))
            if r > best_r:
                best_p, best_r = p, r
        cost = v1.body_tokens(name)
        if chosen and (best_r < ENGAGE or spent + cost > budget):
            reserve.append(name)
            why[name] = 'over the token budget' if spent + cost > budget else 'no job left that it suits (weak response)'
            continue
        chosen.append((name, best_p, best_r))
        spent += cost
        need[best_p] *= 1 - WORK_DONE * best_r
    for n in pool:
        why.setdefault(n, 'not reached: the stack was full (max skills)')
    reserve += sorted(pool, key=lambda n: -pool[n])[:5]
    return chosen, reserve, spent, need


# ----------------------------------------------------------------- history

class History(v1.Markov):
    """What usually follows each skill: a Markov chain smoothed by category and job, whose recorded
    counts decay with a half-life of HALF_LIFE_DAYS. The recipes are permanent."""

    def __init__(self, recipes=(), events=(), now=None):
        super().__init__(recipes, [])
        now = now or time.time()
        for seq, t in self._sessions(list(events)):
            w = math.exp(-max(0.0, now - t) / 86400.0 * math.log(2) / HALF_LIFE_DAYS)
            for a, b in zip(seq, seq[1:]):
                if a == b or a not in core.SKILLS or b not in core.SKILLS:
                    continue
                self.c.setdefault(a, {})
                self.c[a][b] = self.c[a].get(b, 0) + w
                self.total[a] = self.total.get(a, 0) + w
                ca, cb = core.SKILLS[a]['category'], core.SKILLS[b]['category']
                self.cat_c.setdefault(ca, {})
                self.cat_c[ca][cb] = self.cat_c[ca].get(cb, 0) + w
                self.cat_total[ca] = self.cat_total.get(ca, 0) + w

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


# ---------------------------------------------------------------- selection

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


def select(task, project=None, goal=None, after=(), budget=12000, max_skills=4, history=None, scan_result=None,
           model=None, want_signals=False, include=(), exclude=(), explain=False, phase_hint=None):
    """Decide which skills to use for a task, and in what order.

    `model` is a learned preference model (sfp_learn.Model); without one, or with one that has seen
    no feedback, the result is the same as the unlearned selection.
    `exclude` names skills the user ruled out; `include` names skills the user pinned, which join the stack
    whatever their score. `explain` adds the top candidates, their signal votes and why each was or was not taken.
    `phase_hint` is the phase of work observed from activity (sfp_track): {phase: share}. It is blended with
    what the task's words say, half and half, or used alone when the words say nothing about the phase.
    """
    t0 = time.time()
    after = [n for n in (core.resolve_name(a) for a in (after or [])) if n]
    exclude = {n for n in (core.resolve_name(x) for x in (exclude or [])) if n}
    include = [n for n in (core.resolve_name(x) for x in (include or [])) if n and n not in INTERNAL_SKILLS]
    hist = history if history is not None else History(v1.RECIPES, v1.read_usage())
    sc = scan_result if scan_result is not None else scan(project)
    sit = read_situation(task, goal, sc)
    phase_queries = []
    if phase_hint:
        hint = {p: float(v) for p, v in phase_hint.items() if p in v1.PHASE_ORDER and v > 0}
        top = max(hint.values()) if hint else 0
        if top:
            lead = max(hint, key=hint.get)
            phase_queries = [(' '.join(v1.PHASE_WORDS[lead].split()[:4]), 0.7)]
            hint = {p: v / top for p, v in hint.items()}
            said = sit['demand']
            sit['demand'] = {p: (0.5 * said.get(p, 0) + 0.5 * hint.get(p, 0)) if said else hint.get(p, 0)
                             for p in set(said) | set(hint)}
    tech = sorted(sit['ctx_tech'], key=lambda t: (-sit['ctx'][t], t))[:3]

    words = sit['words'][:sel_words()]
    recalled = {}
    if model is not None and model.w:
        recalled = {n: z for n, z in model.recall(words).items() if z >= RECALL and n not in after and n not in INTERNAL_SKILLS}
    votes = collect_signals(sit, after, hist, recalled, phase_queries)
    learned = {}
    quality = {}
    for n, v in votes.items():
        z = model.preference(n, words) if model is not None else 0.0
        if z:
            learned[n] = z
        if has_agreement(v) or (z >= RESCUE and v['words'] and v['relation'] != 'mismatch'):
            quality[n] = base_quality(v) * (math.exp(z) if z else 1.0)
    for n in exclude:
        quality.pop(n, None)
    if quality:
        top_q = max(quality.values())
        quality = {n: q / top_q for n, q in quality.items()}
    why = {}
    pinned = [n for n in include if n not in exclude]
    rest = {n: q for n, q in quality.items() if n not in pinned}
    chosen, reserve, spent, left = assemble(rest, sit['demand'], budget, max(0, max_skills - len(pinned)), why)
    for n in pinned:
        # The user's choice: it takes the job it suits best, and is listed with the others.
        aff = affinity(n)
        phase = max(v1.PHASE_ORDER, key=lambda p: aff[p])
        chosen.append((n, phase, 1.0))
        spent += v1.body_tokens(n)
        quality.setdefault(n, 0.0)
        votes.setdefault(n, {'words': 0.0, 'project': None, 'role': None, 'category': None, 'history': None, 'relation': 'general'})

    stack = []
    for name, phase, resp in chosen:
        v = votes[name]
        reasons = []
        hit = sorted(set(sit['words']) & v1.SKILL_TOKENS.get(name, set()))
        if hit:
            reasons.append('task words: ' + ', '.join(sit['said'].get(w, w) for w in hit[:4]))
        skill_tech = v1.SKILL_TECH.get(name, set())
        if v['relation'] == 'fit':
            reasons.append('fits project: ' + ', '.join(v1.show(sorted(skill_tech & sit['ctx_tech'])[:3])))
        elif v['relation'] == 'near':
            reasons.append('suits the project language')
        if v['history']:
            reasons.append('often follows ' + after[-1])
        if learned.get(name, 0) >= 0.15:
            reasons.append('preferred from feedback')
        elif learned.get(name, 0) <= -0.15:
            reasons.append('down-weighted by feedback')
        if name in pinned:
            reasons.insert(0, 'pinned by you')
        else:
            reasons.append('backed by: ' + ', '.join(backers(v)))
        stack.append({'name': name, 'phase': phase, 'layer': v1.LAYER[phase], 'category': core.SKILLS[name]['category'],
                      'tokens': v1.body_tokens(name), 'score': round(quality[name], 3), 'support': len(backers(v)),
                      'response': round(resp, 3), 'relevance': round(v['words'], 3),
                      'path': core.SKILLS[name]['path'] + '/SKILL.md', 'reasons': reasons})
    stack.sort(key=lambda c: (v1.PHASE_ORDER.index(c['phase']), -c['score']))

    used = {c['name'] for c in stack}
    recipe, best = None, 0.0
    for rc in v1.RECIPES:
        shared = len(used & set(rc['skills'])) / max(1, min(len(used), len(rc['skills'])))
        gw = set(core.tokens(rc['goal']))
        val = max(shared, len(set(sit['words']) & gw) / max(1, len(gw)))
        if val > best and val >= 0.5:
            recipe, best = rc, val
    nxt = []
    if stack:
        last = stack[-1]['name']
        for p, b in hist.next(last, limit=40, exclude=used | set(after)):
            if relation(v1.SKILL_TECH.get(b, set()), sit['ctx_tech']) != 'mismatch':
                nxt.append({'name': b, 'probability': round(p, 4)})
            if len(nxt) == 3:
                break

    ctx = sit['ctx']
    layers = {'base': [], 'check': [], 'finish': []}
    for c in stack:
        layers[c['layer']].append(c['name'])

    res = {
        'engine': 'sfp-hive ' + VERSION,
        'task': task, 'goal': goal,
        'project': {'technologies': v1.show(sorted(sit['ctx_tech'], key=lambda t: (-ctx[t], t))[:8]),
                    'evidence': sc['signals'][:8], 'files_scanned': sc['files']},
        'phases': {p: round(v, 2) for p, v in sorted(sit['demand'].items(), key=lambda kv: -kv[1])},
        'layers': layers,
        'stack': stack,
        'tokens': spent,
        'recipe': recipe and {'name': recipe['name'], 'skills': recipe['skills']},
        'next': nxt,
        'analysis': {'candidates': len(votes), 'agreed': len(quality), 'reserve': reserve[:5],
                     # jobs the task asked for that no chosen skill took up in earnest
                     'unmet': {p: round(sit['demand'][p], 2) for p in sit['demand']
                               if sit['demand'][p] >= 0.25 and
                               left[p] >= 0.75 * (BASE_DEMAND + (1 - BASE_DEMAND) * sit['demand'][p])}},
        'considered': len(votes),
        'ms': int((time.time() - t0) * 1000),
    }
    if pinned or exclude:
        res['intervention'] = {'pinned': pinned, 'excluded': sorted(exclude)}
    if explain:
        taken = {c['name'] for c in stack}
        agreed = sorted(quality, key=lambda n: -quality[n])[:12]
        others = sorted((n for n in votes if n not in quality and n not in exclude), key=lambda n: -(votes[n]['words'] or 0))[:6]
        rows = []
        for n in list(dict.fromkeys([c['name'] for c in stack] + agreed + others + sorted(exclude & set(votes)))):
            v = votes.get(n, {})
            if n in taken:
                status = 'pinned by you' if n in pinned else 'chosen'
            elif n in exclude:
                status = 'excluded by you'
            elif v.get('relation') == 'mismatch':
                status = 'dropped: for another technology than the project'
            elif n not in quality:
                status = 'dropped: no agreement (task words too weak, and fewer than two signals backed it)'
            else:
                status = 'dropped: ' + why.get(n, 'not reached')
            rows.append({'name': n, 'status': status, 'quality': round(quality.get(n, 0.0), 3),
                         'signals': {k: (None if v.get(k) is None else round(v[k], 3)) for k in SIGNALS},
                         'backers': backers(v) if v else [], 'relation': v.get('relation'),
                         'learned': round(learned.get(n, 0.0), 3), 'tokens': v1.body_tokens(n)})
        res['explain'] = rows
    if want_signals:
        # What the learner needs to remember about this decision: numbers only, no text from the task.
        res['_record'] = {'tech': tech, 'words': words, 'phases': {p: round(v, 2) for p, v in sit['demand'].items()},
                          'candidates': {n: {k: (None if votes[n][k] is None else round(votes[n][k], 3)) for k in SIGNALS}
                                         for n in sorted(quality, key=lambda n: -quality[n])[:25]}}
    return res


def sel_words():
    """How many of the task's words the learner looks at."""
    return 12


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


SETS = (('bench', None), ('proj', 'stack_eval.json'), ('fresh', 'hive_heldout.json'))


def load_cases(tests_dir, tmp, only=None):
    """The task sets as (key, cases); each case has a task, expect, avoid and a project folder (or None)."""
    out = []
    for key, fname in SETS:
        if only and key not in only:
            continue
        if fname is None:
            cases = []
            for name in ('search_eval.json', 'search_holdout.json', 'search_fresh.json'):
                path = os.path.join(tests_dir, name)
                if os.path.isfile(path):
                    cases += [dict(c, project=None, avoid=c.get('avoid', [])) for c in _load(path)]
        else:
            path = os.path.join(tests_dir, fname)
            if not os.path.isfile(path):
                continue
            data = _load(path)
            _projects(data, os.path.join(tmp, key))
            cases = [dict(c, project=os.path.join(tmp, key, c['project'])) for c in data['cases']]
        if cases:
            out.append((key, cases))
    return out


def evaluate(tests_dir=None, only=None):
    """Score the hive, the v1 engine and plain search on the task sets. Used by the tests and the README."""
    import tempfile
    tests_dir = tests_dir or os.path.join(os.path.dirname(HERE), 'tests')
    hist = History(v1.RECIPES, [])  # recipes only, so personal usage never changes the published figures
    old = v1.Markov(v1.RECIPES, [])
    engines = {'select': lambda t, p: select(t, p, history=hist), 'v1': lambda t, p: v1.recommend(t, p, chain=old)}
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for key, cases in load_cases(tests_dir, tmp, only):
            n = len(cases)
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
            k = max(1, round(out['%s_select' % key]['size']))
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
    info = res.get('analysis') or {}
    if info:
        lines.insert(-1, 'Hive: %d scouted, %d reached quorum, %d took a job.' % (info['candidates'], info['agreed'], len(res['stack'])))
        if info.get('unmet'):
            lines.insert(-1, 'No skill took: %s' % ', '.join(info['unmet']))
    if res.get('decision'):
        lines.insert(-1, 'Decision %s. Tell it what helped: sfp_hive.py feedback %s --helped <skill> --unhelpful <skill>'
                     % (res['decision'], res['decision']))
    return '\n'.join(lines)


def main(argv=None):
    import argparse
    import sfp_learn
    ap = argparse.ArgumentParser(description='Choose the skills a task needs, and learn from feedback.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('select', help='choose the skills for a task')
    r.add_argument('task')
    r.add_argument('--project')
    r.add_argument('--goal')
    r.add_argument('--after', default='', help='comma-separated skills already used, most recent last')
    r.add_argument('--budget', type=int, default=12000)
    r.add_argument('--max', type=int, default=4)
    r.add_argument('--engine', choices=['select', 'v1'], default='select', help='v1 is the earlier weighted-score engine')
    r.add_argument('--no-learning', action='store_true', help='ignore what feedback has taught the model')
    r.add_argument('--include', default='', help='comma-separated skills to pin into the stack')
    r.add_argument('--exclude', default='', help='comma-separated skills to rule out')
    r.add_argument('--bundle', default='', help='pin all the skills of a bundle (an id or a name from `library`)')
    r.add_argument('--explain', action='store_true', help='add each top candidate, its signal votes and why it was or was not taken')
    r.add_argument('--no-needs', action='store_true', help='do not add skills for what the model cannot do alone (3D, web, limits...)')
    r.add_argument('--check', action='store_true', help='also check the programs and keys the needs depend on')
    r.add_argument('--json', action='store_true')
    f = sub.add_parser('feedback', help='tell the hive what helped, what did not, and what was missing')
    f.add_argument('decision', help='the decision id printed by select, or "last"')
    f.add_argument('--helped', default='', help='comma-separated skills that helped')
    f.add_argument('--unhelpful', default='', help='comma-separated skills that did not help')
    f.add_argument('--ignored', default='', help='comma-separated skills that were chosen but never used')
    f.add_argument('--missing', default='', help='comma-separated skills that should have been chosen')
    f.add_argument('--task', help='the task words, only needed to teach a missing skill the hive could not reach')
    st = sub.add_parser('status', help='what the hive has learned, and how well it is doing')
    st.add_argument('--json', action='store_true')
    sub.add_parser('forget', help='delete everything the hive has recorded and learned')
    n = sub.add_parser('next', help='the skills that usually follow one')
    n.add_argument('skill')
    n.add_argument('--limit', type=int, default=5)
    p = sub.add_parser('profile', help='show what is detected in a project')
    p.add_argument('path', nargs='?', default='.')
    sub.add_parser('recipes', help='list the named stacks')
    sub.add_parser('evaluate', help='score the hive against the earlier engine and plain search')
    sub.add_parser('learning-curve', help='measure whether learning from feedback improves held-out tasks')
    tk = sub.add_parser('track', help='follow the agent: read activity events, estimate the phase, predict the next')
    tk.add_argument('--events', default='-', help='a JSON list of events, or one JSON event per line; - reads stdin')
    tk.add_argument('--no-select', action='store_true', help='only the phase, no skills')
    tk.add_argument('--project')
    tk.add_argument('--max', type=int, default=4)
    tk.add_argument('--reset', action='store_true', help='forget the current tracking state first (learned transitions stay)')
    tk.add_argument('--json', action='store_true')
    lb = sub.add_parser('library', help='every skill by purpose, cluster and bundle, in one JSON object, for the editor')
    lb.add_argument('--json', action='store_true')
    ba = sub.add_parser('bundle-add', help='add or replace a bundle of your own')
    ba.add_argument('name')
    ba.add_argument('--skills', required=True, help='comma-separated skills, in the order to use them')
    ba.add_argument('--goal', default='')
    ba.add_argument('--purpose', default='build')
    ba.add_argument('--when', default='')
    br = sub.add_parser('bundle-remove', help='remove a bundle of your own')
    br.add_argument('name')
    bl = sub.add_parser('bundles', help='list the bundles')
    bl.add_argument('--json', action='store_true')
    cl = sub.add_parser('clusters', help='the skills grouped into clusters, with what has been used')
    cl.add_argument('--json', action='store_true')
    ca = sub.add_parser('cluster-add', help='add or replace a cluster of your own')
    ca.add_argument('name')
    ca.add_argument('--skills', required=True, help='comma-separated skills')
    ca.add_argument('--description', default='')
    cr = sub.add_parser('cluster-remove', help='remove a cluster of your own')
    cr.add_argument('name')
    nd = sub.add_parser('needs', help='what a task needs that the model cannot do alone, and what is missing for it')
    nd.add_argument('task')
    nd.add_argument('--project')
    nd.add_argument('--check', action='store_true', help='check the programs and keys (runs their --version)')
    nd.add_argument('--json', action='store_true')
    lv = sub.add_parser('live', help='attach skills to a message while it is being typed')
    lv.add_argument('draft')
    lv.add_argument('--state', default='', help='the state a previous call printed, as JSON')
    lv.add_argument('--project')
    lv.add_argument('--max', type=int, default=4)
    lv.add_argument('--pin', default='')
    lv.add_argument('--unpin', default='')
    lv.add_argument('--remove', default='')
    lv.add_argument('--restore', default='')
    lv.add_argument('--commit', action='store_true', help='the message was sent: record the decision')
    lv.add_argument('--json', action='store_true')
    tr = sub.add_parser('train', help='train the hive learning model from the benchmark task suites')
    tr.add_argument('--reset', action='store_true', help='reset prior feedback before training')
    tr.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)

    if a.cmd == 'select':
        after = [x for x in a.after.split(',') if x.strip()]
        if a.engine == 'v1':
            res = v1.recommend(a.task, a.project, a.goal, after, a.budget, a.max)
        else:
            include = [x.strip() for x in a.include.split(',') if x.strip()]
            bundle = None
            if a.bundle:
                import sfp_library
                bundle = sfp_library.find_bundle(a.bundle)
                if not bundle:
                    raise SystemExit('no bundle %r. `sfp_hive.py bundles` lists them.' % a.bundle)
                include = list(dict.fromkeys(bundle['skills'] + include))
            exclude = [x.strip() for x in a.exclude.split(',') if x.strip()]
            if a.no_needs:
                res = sfp_learn.decide(a.task, a.project, a.goal, after, a.budget, max(a.max, len(include)), learn=not a.no_learning,
                                       include=include, exclude=exclude, explain=a.explain)
            else:
                import sfp_needs
                res = sfp_needs.decide(a.task, a.project, a.goal, after, a.budget, max(a.max, len(include)), include=include,
                                       exclude=exclude, explain=a.explain, check=a.check, learn=not a.no_learning)
            if bundle:
                res['bundle'] = {'id': bundle['id'], 'name': bundle['name']}
        print(json.dumps(res, indent=1) if a.json else format_stack(res))
    elif a.cmd == 'feedback':
        helped, bad, ignored, missing = ([x.strip() for x in s.split(',') if x.strip()]
                                         for s in (a.helped, a.unhelpful, a.ignored, a.missing))
        print(json.dumps(sfp_learn.give_feedback(a.decision, helped=helped, unhelpful=bad, ignored=ignored,
                                                 missing=missing, task=a.task), indent=1))
    elif a.cmd == 'status':
        st_ = sfp_learn.status()
        print(json.dumps(st_, indent=1) if a.json else sfp_learn.format_status(st_))
    elif a.cmd == 'forget':
        print(json.dumps(sfp_learn.forget()))
    elif a.cmd == 'track':
        import sfp_track
        if a.reset:
            sfp_track.reset()
        raw = sys.stdin.read() if a.events == '-' else open(a.events, encoding='utf-8').read()
        raw = raw.strip()
        events = json.loads(raw) if raw.startswith('[') else [json.loads(x) for x in raw.splitlines() if x.strip()]
        res = sfp_track.track(events, select=not a.no_select, max_skills=a.max, project=a.project)
        if a.json:
            print(json.dumps(res, indent=1))
        else:
            print('Phase: %s (%s layer), confidence %.2f' % (res['phase'], res['layer'], res['confidence']))
            if res.get('next'):
                print('Next, likely: ' + ', '.join('%s %.0f%%' % (n['phase'], 100 * n['probability']) for n in res['next']))
            for c in res.get('skills', []):
                print('  %s (%s)' % (c['name'], c['phase']))
    elif a.cmd == 'needs':
        import sfp_needs
        terms = list(scan(a.project).get('terms', {})) if a.project else []
        found = sfp_needs.needs(a.task, terms, check=a.check)
        print(json.dumps(found, indent=1) if a.json else sfp_needs.format_needs(found))
    elif a.cmd == 'live':
        import sfp_live
        split = lambda v: [x.strip() for x in v.split(',') if x.strip()]
        res = sfp_live.live(a.draft, json.loads(a.state) if a.state else None, a.project, a.max, split(a.pin), split(a.unpin),
                            split(a.remove), split(a.restore), a.commit)
        print(json.dumps(res, indent=1) if a.json else sfp_live.format_live(res))
    elif a.cmd == 'library':
        import sfp_library
        print(json.dumps(sfp_library.library(), separators=(',', ':')))
    elif a.cmd == 'bundles':
        import sfp_library
        res = sfp_library.bundles()
        print(json.dumps(res, indent=1) if a.json else '\n'.join(
            '%-28s %-9s %2d skills%s' % (b['id'], b['purpose'], len(b['skills']), '  [yours]' if b['mine'] else '') for b in res))
    elif a.cmd == 'bundle-add':
        import sfp_library
        print(json.dumps(sfp_library.add_user_bundle(a.name, [x.strip() for x in a.skills.split(',') if x.strip()], a.goal, a.purpose, a.when)))
    elif a.cmd == 'bundle-remove':
        import sfp_library
        print(json.dumps(sfp_library.remove_user_bundle(a.name)))
    elif a.cmd in ('clusters', 'cluster-add', 'cluster-remove'):
        import sfp_clusters
        if a.cmd == 'cluster-add':
            print(json.dumps(sfp_clusters.add_user_cluster(a.name, [x.strip() for x in a.skills.split(',') if x.strip()], a.description)))
        elif a.cmd == 'cluster-remove':
            print(json.dumps(sfp_clusters.remove_user_cluster(a.name)))
        else:
            res = sfp_clusters.clusters(with_usage=True)
            print(json.dumps(res, indent=1) if a.json else sfp_clusters.format_clusters(res))
    elif a.cmd == 'train':
        res = sfp_learn.train_from_benchmarks(reset=a.reset)
        if a.json:
            print(json.dumps(res, indent=1))
        else:
            print('Trained on %d cases (%d tasks with feedback):' % (res['cases_processed'], res['tasks_trained']))
            print('  Decisions logged: %d' % res['decisions_logged'])
            print('  Verdicts recorded: %d' % res['verdicts_recorded'])
            print('  Learned associations: %d (%d training examples)' % (res['model_associations'], res['model_examples']))
    elif a.cmd == 'next':
        name = core.resolve_name(a.skill)
        if not name:
            raise SystemExit('no skill named %r' % a.skill)
        for pr, b in sfp_learn.load_history().next(name, a.limit):
            print('%-40s %.3f' % (b, pr))
    elif a.cmd in ('profile', 'recipes'):
        v1.main([a.cmd] + ([a.path] if a.cmd == 'profile' else []))
    elif a.cmd == 'evaluate':
        print(json.dumps({k: {m: round(x, 3) if isinstance(x, float) else x for m, x in v.items()}
                          for k, v in evaluate().items()}, indent=1))
    elif a.cmd == 'learning-curve':
        print(json.dumps(sfp_learn.learning_curve(), indent=1))


if __name__ == '__main__':
    main()
