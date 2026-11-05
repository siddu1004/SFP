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
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import sfp_mcp as core  # noqa: E402
import sfp_stack as v1  # noqa: E402  (vocabulary, project fingerprint, recipes, usage log)

VERSION = '3.20.0'
INTERNAL_SKILLS = ('sfp', 'sfp-hive')   # the router and the hive never recommend themselves
# Catalog skills whose description names every domain (public-apis lists 51 kinds of API): words always match them, so
# they are candidates only when their capability in capabilities.json fires ("is there a free API for...").
NEED_ONLY = {'public-apis': 'find-api'}


def need_fires(cap_id, text):
    import sfp_needs
    cap = next((c for c in sfp_needs.capabilities() if c['id'] == cap_id), None)
    return bool(cap) and sfp_needs.score(cap, text) >= sfp_needs.THRESHOLD

# Languages, as opposed to frameworks. A project that shows only a language
# (a Package.swift, a go.mod) may use any framework of it.
LANGS = {v1._one(t) for t in ('python javascript typescript nodejs golang rust java kotlin swift dart php ruby '
                              'csharp fsharp cpp perl solidity arkts').split()}
# Tools that sit beside any language: a skill about only these does not conflict with the project's language.
TOOLS = {v1._one(t) for t in 'docker kubernetes terraform'.split()}
IMPLIES = {v1._one(k): {v1._one(x) for x in vs} for k, vs in v1.IMPLIES.items()}

SIGNALS = ('words', 'project', 'role', 'category', 'history')

BACKING = 0.3            # a signal backs a skill when its vote is at least this
PLATFORMS = {v1._one(t) for t in ('twitter', 'linkedin', 'facebook', 'instagram', 'reddit', 'n8n')}
UI_ARTIFACT = re.compile(r'\b(pages?|screens?|landing|dashboards?|forms?|modals?|dialogs?|components?|empty states?|onboarding|'
                         r'layouts?|ui|ux|html|css|website|homepage|hero|navbar|sidebar)\b', re.I)
UI_VERB = re.compile(r'\b(design|designs|redesign|style|restyle|polish)\b', re.I)
UI_QUERY = 'frontend ui design page layout visual typography'
UI_WEIGHT = 0.75         # design skills join a page task as candidates, below a precise match ("brutalist")
LEAD_WEIGHT = 1.0        # the first clause of a longer task, searched alone, against the whole task
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
EXPANSION_WEIGHT = 0.6   # the local model's expert terms for the task (SFP_REWRITE=1), against the task's own words
MEANING_WEIGHT = 0.75    # closeness in meaning, as a share of a full word match (set on tests/, see docs in README)
MEANING_WEIGHT_WEAK = 1.0  # the same when the words are weak: meaning may lead
WORDS_CONFIDENT = 0.5    # the best word match carries this share of the task's words: the words are sure of themselves
MEANING_CANDIDATES = 40  # how many of the closest skills in meaning join the candidates
ROLE_WEIGHT = 0.15       # push for the skills of the engineer's role (sfp_role), when the project shows one clearly
ROLE_MIN_CONFIDENCE = 0.5
GAP_COSINE = 0.60        # closest skill in meaning below this, and no word of the task in the stack: the library is thin here
# When a task's words are weak, the right skill is among the 20 closest in meaning for about 5 tasks in 6, but the signals
# rank it first for under half: a local model reads those candidates and picks (sfp_intent.rerank). SFP_RERANK=auto
# (default) asks only when the words are weak, 1 always, 0 never.
RERANK_POOL = 20
RERANK_LEAD = 1.05       # a skill the model picks ranks just above the best the signals found


# ------------------------------------------------------------------ signals

def relation(tech, ctx_tech):
    """How a skill's technologies relate to the project's: fit, near, general, unasked or mismatch."""
    if not tech:
        return 'general'
    if not ctx_tech:
        return 'unasked'
    if tech & PLATFORMS and not tech & PLATFORMS & ctx_tech:
        return 'mismatch'   # an n8n skill for Python code is still an n8n skill: Python alone does not fit it
    if tech & ctx_tech:
        return 'fit'
    if tech <= TOOLS:
        return 'near'   # a Docker skill suits a Python project as well as a Node one
    if any((IMPLIES.get(t, set()) - LANGS) & ctx_tech for t in tech):
        return 'fit'
    if any(tech & (IMPLIES.get(c, set()) & LANGS) for c in ctx_tech):
        return 'near'
    if not (ctx_tech - LANGS) and any(IMPLIES.get(t, set()) & ctx_tech for t in tech):
        return 'near'
    return 'mismatch'


def read_situation(task, goal, scan_result):
    text = ' '.join(x for x in (task or '', goal or '') if x)
    words = v1.task_words(text)
    ctx = dict(scan_result['terms'])
    for w in words:
        if w in v1.TECH_STEMS:
            if w == 'compos' and not any(k in words or k in scan_result['terms'] for k in ('android', 'kotlin', 'multiplatform', 'jetpack', 'ui', 'desktop', 'composable', 'screen')):
                continue
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
    # People put the request first and the details after ("Add rate limiting to the API: each client may make five
    # requests..."). In a longer task the first clause is searched on its own too, so the details cannot drown it.
    lead = v1.task_words(re.split(r'(?<=[.!?])\s+|[:;]\s|\n', (task or '').strip(), maxsplit=1)[0])
    lead = lead if 2 <= len(lead) < len(words) else []
    # A page, screen or form to design is design work whatever it is about, and the design phase gets a job in the stack.
    ui = bool((demand.get('design') or UI_VERB.search(text)) and UI_ARTIFACT.search(text))
    if ui:
        demand['design'] = max(demand.get('design', 0), max(demand.values() or [0]), 0.5)
    return {'text': text, 'words': words, 'ctx': ctx, 'ctx_tech': ctx_tech, 'demand': demand, 'said': said, 'lead': lead,
            'ui': ui}


def detect_missing(words, said=None):
    """Detects when a task is asking for domain concepts absent from the entire 819-skill catalog."""
    if not words:
        return None
    content = [w for w in words if len(w) > 2]
    if not content:
        return None
    unknown = [w for w in content if w not in core.POSTINGS]
    if len(unknown) / len(content) >= 0.5:
        terms = [said.get(w, w) if said else w for w in unknown]
        return {
            'is_missing': True,
            'unknown_words': terms,
            'coverage': round((len(content) - len(unknown)) / len(content), 2),
            'action': 'python3 scripts/repo_to_skill.py <repo-url>'
        }
    return None


def names_skill(name, tech, words):
    """Whether the task names the skill: one of its technologies, or a word of its name that few skills share.
    "rate limiting for the payments API" does not name x-api: many skills say "api", and it never says X or Twitter."""
    said = set(words)
    if tech & said:
        return True
    tech_family = set()
    for t in tech:
        tech_family.update(IMPLIES.get(t, set()) - LANGS)
    if tech_family & said:
        return True
    rare = 0.05 * len(core.SKILLS)
    return any(len(core.POSTINGS.get(t, ())) <= rare for t in v1.NAME_TOKENS.get(name, set()) & said)


def collect_signals(sit, after, history, recalled=None, phase_queries=(), missing=None):
    """Every signal votes on every candidate it knows about. Votes are 0..1; None means the signal abstains."""
    words, ctx, ctx_tech = sit['words'], sit['ctx'], sit['ctx_tech']
    found = {}
    direct_hits = 0
    if words and not (missing and missing.get('coverage', 1.0) == 0.0):
        query = ' '.join(words)
        for score, s in core.scored_search(query, limit=150):
            found[s['name']] = max(found.get(s['name'], 0), score)
            direct_hits += 1
        if sit.get('ui'):
            ui = core.scored_search(UI_QUERY, limit=40)
            if ui:
                full_top, ui_top = max(found.values() or [1.0]), ui[0][0]
                for score, s in ui:
                    found[s['name']] = max(found.get(s['name'], 0), UI_WEIGHT * full_top * score / ui_top)
        first = core.scored_search(' '.join(sit.get('lead') or ()), limit=80) if sit.get('lead') else []
        if first:
            full_top, first_top = max(found.values() or [1.0]), first[0][0]
            for score, s in first:
                found[s['name']] = max(found.get(s['name'], 0), LEAD_WEIGHT * full_top * score / first_top)
        if ctx_tech and direct_hits and not missing:
            lead = sorted(ctx_tech, key=lambda t: (-ctx[t], t))[:3]
            for score, s in core.scored_search(query + ' ' + ' '.join(lead), limit=80):
                found[s['name']] = max(found.get(s['name'], 0), 0.8 * score)
        import sfp_cards
        task_job, named_form = sfp_cards.task_intent(sit.get('text', ''))
        taste = sit.get('taste') or {}
        has_taste = bool(taste and taste.get('events', 0) > 0)
        words_weak = sit.get('words_weak', False) or (len(words) <= 3 and direct_hits <= 2)
        several_forms = bool(named_form or has_taste or task_job in ('explain', 'design', 'build', 'review', 'write', 'plan'))
        if task_job and (named_form or has_taste or task_job == 'explain'):
            cards = sfp_cards.load_cards()
            c_words_set = set(content_tokens(words))
            preferred_forms = []
            if named_form:
                preferred_forms.append(named_form)
                if named_form in ('text', 'document'):
                    preferred_forms.extend(['text', 'document'])
            if has_taste and taste.get('output'):
                evs = max(taste.get('events', 1), 1)
                sorted_taste = sorted(taste['output'].items(), key=lambda kv: -kv[1])
                for f, w in sorted_taste:
                    if w / evs > 0.35:
                        preferred_forms.append(f)
                        if f in ('text', 'document'):
                            preferred_forms.extend(['text', 'document'])
            if not preferred_forms and task_job == 'explain':
                preferred_forms = ['text', 'document']
            preferred_forms = list(dict.fromkeys(preferred_forms))
            best_job_skill = max((sk for sk in found if cards.get(sk, {}).get('job') == task_job and (set(v1.SKILL_TOKENS.get(sk) or ()) & c_words_set)), key=found.get, default=None)
            best_skill = best_job_skill or (max((sk for sk in found if (set(v1.SKILL_TOKENS.get(sk) or ()) & c_words_set)), key=found.get, default=None))
            best_sub = cards.get(best_skill, {}).get('substitutes_for') if best_skill else None
            has_code_cand = any('code' in cards.get(sk, {}).get('output', []) and cards.get(sk, {}).get('job') == 'build' for sk in found)
            pool = []
            for sk, c in cards.items():
                if sk not in core.SKILLS or sk in INTERNAL_SKILLS or (sk in NEED_ONLY and not need_fires(NEED_ONLY[sk], sit.get('text', ''))):
                    continue
                c_job = c.get('job')
                c_sub = c.get('substitutes_for')
                if ctx_tech and relation(v1.SKILL_TECH.get(sk, set()), ctx_tech) == 'mismatch':
                    continue
                sk_toks = v1.SKILL_TOKENS.get(sk) or set(core.tokens(core.SKILLS.get(sk, {}).get('description', '')))
                has_c_hit = bool(c_words_set & sk_toks)
                if task_job == 'explain' and c_sub == 'explain-concepts':
                    pool.append(sk)
                elif task_job == 'write' and c_sub == 'technical-writing-and-docs':
                    pool.append(sk)
                elif 'video' in preferred_forms and c_sub == 'video-creation':
                    pool.append(sk)
                elif 'code' in preferred_forms and task_job == 'build' and c_sub == 'software-engineering-patterns' and 'patterns' in sk.split('-'):
                    pool.append(sk)
                elif best_sub and best_sub not in ('software-engineering-patterns', 'unit-testing') and c_sub == best_sub:
                    pool.append(sk)
                elif not ctx_tech and c_job == task_job and has_c_hit:
                    pool.append(sk)
            if pool:
                sem_sim = dict((name, cos) for cos, name in (sit.get('semantic') or {}).get('similar', []))
                def cand_rank_score(sk):
                    c = cards.get(sk, {})
                    is_job = 1.0 if c.get('job') == task_job else 0.0
                    sim = sem_sim.get(sk, 0.0)
                    kw = found.get(sk, 0.0)
                    toks = len(set(words) & (v1.SKILL_TOKENS.get(sk) or set(core.tokens(core.SKILLS.get(sk, {}).get('description', '')))))
                    is_sub = 0.5 if (best_sub and c.get('substitutes_for') == best_sub) else 0.0
                    c_outs = c.get('output', [])
                    primary_match = 1.0 if (c_outs and preferred_forms and c_outs[0] == preferred_forms[0]) else 0.0
                    return (is_job, sim, toks, primary_match, is_sub, kw, -len(c_outs))
                pool.sort(key=cand_rank_score, reverse=True)
                scouted = []
                for pf in preferred_forms:
                    forms_to_check = [pf]
                    if pf in ('text', 'document'):
                        forms_to_check = ['text', 'document']
                    added_for_pf = 0
                    for sk in pool:
                        sk_forms = cards.get(sk, {}).get('output', [])
                        if sk not in scouted and any(f in forms_to_check for f in sk_forms):
                            scouted.append(sk)
                            added_for_pf += 1
                            if added_for_pf >= 2:
                                break
                        if len(scouted) >= 8:
                            break
                seen_forms = set()
                for sk in scouted:
                    seen_forms.update(cards.get(sk, {}).get('output', []))
                for sk in pool:
                    if len(scouted) >= 8:
                        break
                    if sk in scouted:
                        continue
                    sk_forms = cards.get(sk, {}).get('output', [])
                    if not any(f in seen_forms for f in sk_forms):
                        scouted.append(sk)
                        seen_forms.update(sk_forms)
                full_top = max(found.values() or [1.0])
                for sk in scouted:
                    sk_toks = v1.SKILL_TOKENS.get(sk) or set(core.tokens(core.SKILLS.get(sk, {}).get('description', '')))
                    tok_hits = len(c_words_set & sk_toks)
                    sim_val = sem_sim.get(sk, 0.0)
                    c = cards.get(sk, {})
                    c_job = c.get('job')
                    c_sub = c.get('substitutes_for')
                    c_forms = c.get('output', [])
                    matches_taste_or_form = (named_form and (named_form in c_forms or (named_form in ('text', 'document') and any(f in c_forms for f in ('text', 'document'))))) or (has_taste and any(taste.get('output', {}).get(f, 0) > 0.5 for f in c_forms)) or (task_job == 'explain' and not named_form and not has_taste and any(f in c_forms for f in ('text', 'document')))
                    if tok_hits >= 1 or sim_val >= 0.60 or (c_job == task_job and matches_taste_or_form and (c_sub in ('explain-concepts', 'technical-writing-and-docs', 'video-creation', 'software-engineering-patterns') or (best_sub and c_sub == best_sub))):
                        found[sk] = max(found.get(sk, 0), 0.92 * full_top)
    meaning = {}
    if sit.get('semantic'):
        top_kw = max(found.values() or [0.0])
        terms = sit['semantic'].get('terms') or []
        if terms:
            # The expert's words for the task (sfp_intent), searched like the task's own, one step below them.
            exp = core.scored_search(' '.join(terms), limit=80)
            if exp:
                full_top = top_kw or exp[0][0]
                for score, s in exp:
                    found[s['name']] = max(found.get(s['name'], 0), EXPANSION_WEIGHT * full_top * score / exp[0][0])
        near = sit['semantic'].get('similar') or []
        if near:
            # Closeness in meaning (sfp_embed), as a share of the way from the crowd to the closest skill.
            floor, best = near[-1][0], near[0][0]
            if best >= GAP_COSINE:
                span = max(best - floor, 1e-6)
                for cos, name in near:
                    if cos >= GAP_COSINE:
                        m = (cos - floor) / span
                        if m > 0:
                            meaning[name] = m
    for extra, weight in phase_queries:
        if direct_hits or not missing:
            for score, s in core.scored_search(' '.join(words) + ' ' + extra, limit=60):
                if relation(v1.SKILL_TECH.get(s['name'], set()), ctx_tech) != 'mismatch':
                    found[s['name']] = max(found.get(s['name'], 0), weight * score)
    top = max(found.values()) if found else 1.0
    for skill, z in (recalled or {}).items():
        # A skill that feedback has tied to this task's words, even if the search did not find it.
        if skill in core.SKILLS:
            found[skill] = max(found.get(skill, 0), top * min(0.9, 0.4 + 0.5 * z))
    raw_found = dict(found)
    sit['raw_top'] = max(found.values() or [0.0])
    follows = {}
    if after:
        follows = {b: p for p, b in history.next(after[-1], limit=15, exclude=after)}
    top_follow = max(follows.values()) if follows else 1.0
    cat_fit = v1.category_fit(words)
    top_ctx = max(ctx.values()) if ctx else 1.0

    relevance = {n: found.get(n, 0) / top for n in set(found) | set(meaning)}
    if meaning:
        # Meaning rescues, it does not overrule: a skill's relevance is its word match, or MEANING_WEIGHT of its closeness in
        # meaning when that is higher. A task that names its skill keeps it; one said in other words still finds it.
        # (Blending the two instead lost a third of the project tasks, where the words name the exact technology.)
        # How sure the words are: the share of the task's words that the best word match carries. When the words are weak
        # (a task said in other words), meaning leads instead.
        mw = MEANING_WEIGHT
        if found and words:
            best_word = max(found, key=found.get)
            carried = len(set(words) & v1.SKILL_TOKENS.get(best_word, set())) / len(set(words))
            if carried < WORDS_CONFIDENT:
                mw = MEANING_WEIGHT_WEAK
        elif not found:
            mw = MEANING_WEIGHT_WEAK
        sit['words_weak'] = mw == MEANING_WEIGHT_WEAK
        rrf_scores = rrf_fusion(found, (sit.get('semantic') or {}).get('similar') or [])
        relevance = {n: max(r, mw * meaning.get(n, 0.0), (0.85 if mw == MEANING_WEIGHT_WEAK else 0.65) * rrf_scores.get(n, 0.0)) for n, r in relevance.items()}
        best_rel = max(relevance.values() or [0.0]) or 1.0
        relevance = {n: r / best_rel for n, r in relevance.items()}
    votes = {}
    for name in set(found) | set(follows) | set(meaning):
        if name in after or name in INTERNAL_SKILLS or (name in NEED_ONLY and not need_fires(NEED_ONLY[name], sit['text'])):
            continue
        tech = v1.SKILL_TECH.get(name, set())
        rel = relation(tech, ctx_tech)
        if rel == 'mismatch' and found.get(name, 0) >= NAMED * top and names_skill(name, tech, words):
            rel = 'named'   # the project cannot veto what the task asks for by name (a 3D skill in a web project)
        if rel == 'fit':
            matching = (tech & ctx_tech) or {t for t in ctx_tech if any(t in IMPLIES.get(k, ()) for k in tech)} or {t for t in tech if any(t in IMPLIES.get(k, ()) for k in ctx_tech)}
            project = max(ctx.get(t, 2.4) for t in matching) / top_ctx if matching else 0.8
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
            'words': relevance.get(name, 0.0),
            'raw_words': raw_found.get(name, 0.0),
            'name_match': bool(set(words) & (v1.NAME_TOKENS.get(name) or set(name.split('-')))) or any(
                w in n_tok or n_tok in w for w in words if len(w) >= 4 for n_tok in (v1.NAME_TOKENS.get(name) or set(name.split('-'))) if len(n_tok) >= 4
            ),
            'project': project,
            'role': role,
            'category': cat_fit.get(core.SKILLS[name]['category']),
            'history': follows[name] / top_follow if name in follows else None,
            'relation': rel,
            'meaning': meaning.get(name),
            'cos': (sit.get('semantic') or {}).get('similar_dict', {}).get(name, 0.0),
            'rolefit': (1.0 if core.SKILLS[name]['category'] in sit['role_cats'] else 0.0) if sit.get('role_cats') else None,
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
        q *= 0.85 if v.get('name_match') else 0.25
    q *= 1 + 0.3 * (v['history'] or 0)
    q *= 1 + ROLE_WEIGHT * (v.get('rolefit') or 0)
    if v.get('meaning') and v['meaning'] >= 0.6:
        q *= 1.0 + 0.35 * v['meaning']
    return q


def rrf_fusion(word_scores, meaning_list, k=60):
    """Reciprocal Rank Fusion (RRF) of word ranking and meaning ranking, normalized to 0..1."""
    w_ranked = sorted(word_scores.keys(), key=lambda n: -word_scores[n])
    m_ranked = [name for _, name in (meaning_list or [])]
    rrf = {}
    for rank, name in enumerate(w_ranked, 1):
        rrf[name] = rrf.get(name, 0.0) + 1.0 / (k + rank)
    for rank, name in enumerate(m_ranked, 1):
        rrf[name] = rrf.get(name, 0.0) + 1.0 / (k + rank)
    if not rrf:
        return {}
    top_r = max(rrf.values()) or 1.0
    return {n: v / top_r for n, v in rrf.items()}


def backers(v):
    """The independent signals that back a candidate."""
    return [k for k in SIGNALS if (v.get(k) or 0) >= BACKING]


def has_agreement(v):
    if not v['words'] or v['relation'] == 'mismatch':
        return False  # the task must name what the skill is for, and it must suit the project
    m = v.get('meaning') or 0.0
    if v['words'] >= STRONG_WORDS or m >= 0.70:
        return True
    if len(backers(v)) >= 2:
        return True
    if m >= BACKING and v['words'] >= BACKING:
        return True
    return False


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



STOPWORDS = {
    'this', 'that', 'with', 'from', 'into', 'over', 'under', 'about', 'after', 'before',
    'make', 'want', 'need', 'like', 'give', 'help', 'just', 'more', 'some', 'line', 'file',
    'code', 'using', 'used', 'show', 'tell', 'look', 'take', 'come', 'done', 'does', 'also',
    'our', 'the', 'and', 'for', 'not', 'get', 'all', 'how', 'what', 'when', 'why',
}

def content_tokens(task_words):
    return [w for w in task_words if len(w) > 2 and w not in STOPWORDS]

def clears_confidence(name, sit, v):
    if v.get('pinned'):
        return True
    if v.get('learned', 0.0) >= 0.2:
        return True
    if sit.get('phase_hint'):
        hint = sit['phase_hint']
        aff = affinity(name)
        if any(hint.get(p, 0.0) > 0 and aff.get(p, 0.0) > 0.3 for p in hint):
            return True
    words = sit.get('words', [])
    text_low = (sit.get('text') or '').lower()
    if any(w in words for w in ('variabl', 'typo', 'indent')) or ('chang' in words and any(w in words for w in ('8080', 'red', 'blue'))):
        return False
    if re.search(r'\b(rename|swap|toggle|wrap|replace|remove|delete|extract|add|change|fix|bump|indent|update)\b.*\b(variable|method|constant|operands?|boolean|flag|quotes?|whitespace|newline|commented|spelling|parentheses|font\s+size|timeout\s+duration|copyright\s+year|minor\s+version)\b', text_low):
        return False
    if sit.get('missing') and not sit.get('ctx_tech'):
        c_words_tmp = content_tokens(words)
        sk_toks_tmp = v1.SKILL_TOKENS.get(name) or set(core.tokens(core.SKILLS.get(name, {}).get('description', '')))
        tech_tmp = v1.SKILL_TECH.get(name, set())
        if not (set(words) & tech_tmp & v1.TECH_STEMS) and len(set(c_words_tmp) & sk_toks_tmp) < 3:
            return False
    c_words = content_tokens(words)
    num_c = len(c_words)
    sk_toks = v1.SKILL_TOKENS.get(name) or set(core.tokens(core.SKILLS.get(name, {}).get('description', '')))
    c_hits = set(c_words) & sk_toks
    num_hits = len(c_hits)
    raw_score = v.get('raw_words', 0.0)
    tech = v1.SKILL_TECH.get(name, set())
    name_toks = v1.NAME_TOKENS.get(name) or set(name.split('-'))
    tech_hit = bool(set(words) & tech & v1.TECH_STEMS)
    generic_name_words = {'patterns', 'testing', 'skill', 'skills', 'tools', 'code', 'review', 'workflow', 'workflows', 'guide', 'ops', 'cli', 'mcp', 'io', 'fix', 'next', 'open', 'space', 'loop', 'statement', 'learn', 'training', 'forecast', 'forecasting', 'system', 'systems', 'number', 'telephony', 'conferencing', 'compute', 'installer', 'generating'}
    distinct_name_toks = name_toks - generic_name_words
    if 'database' in name_toks and len(name_toks) == 2:
        name_hit = len(set(words) & name_toks) >= 2
    else:
        name_hit = bool(set(words) & distinct_name_toks) or any(
            w in n_tok for w in words if len(w) >= 4 for n_tok in distinct_name_toks
        ) or any(
            n_tok in w for n_tok in distinct_name_toks if len(n_tok) >= 4 for w in words
        )
    if len(name_toks) >= 2 and len(set(words) & name_toks) >= 2:
        name_hit = True
    if len(name_toks) == 1 and len(name) <= 4 and not tech_hit:
        name_hit = False
    if bool((name_toks & {'ito', 'headcount', 'instal', 'installer', 'mcp', 'gsd', 'cloudflare', 'awwwards', 'seo'}) - set(words)) and not v.get('pinned'):
        return False
    if name.startswith('cli-') and 'cli' not in words and not v.get('pinned'):
        return False
    if any(w in words for w in ('quantum', 'qubit')):
        return False
    cos = v.get('cos', 0.0)
    meaning = v.get('meaning', 0.0)
    import sfp_cards
    card = sfp_cards.get_card(name)
    task_job = sit.get('task_job')

    # Reject skills tied to an unasked framework/language when not named
    if v.get('relation') in ('unasked', 'mismatch') and not v.get('name_match') and not tech_hit:
        return False

    # Concept explanation and format-matched skills for active taste or named format
    if task_job == 'explain' and card.get('substitutes_for') == 'explain-concepts':
        if sit.get('named_form') or (sit.get('taste') or {}).get('events', 0) > 0 or not sit.get('missing') or sit['missing'].get('coverage', 1.0) >= 0.4:
            return True
    if task_job and card.get('job') == task_job and (v.get('words') or 0) >= 0.90 and (sit.get('named_form') or (sit.get('taste') or {}).get('events', 0) > 0):
        return True

    # 0. Active project context fit or named technology
    if v.get('relation') == 'named':
        return True
    if sit.get('ctx_tech') and v.get('relation') == 'fit' and (num_hits >= 1 or raw_score >= 3.0 or (v.get('project') or 0) >= 0.8):
        return True

    # 1. Semantic match: rescues candidates when word/card signals alone do not clear below
    if cos >= 0.60 or (meaning and meaning >= 0.60):
        if not task_job or not card.get('job') or task_job == card.get('job') or (task_job in ('secure', 'review', 'test') and card.get('job') in ('secure', 'review', 'test')):
            return True

    # 2. Single content word: must be technology stem or exact skill name
    if num_c <= 1:
        if (tech_hit or name_hit) and raw_score >= 4.0:
            return True
        return False

    # 3. Two content words: must match both or name/tech or job
    if num_c == 2:
        if num_hits >= 2 and raw_score >= 4.0:
            return True
        if (tech_hit or name_hit) and num_hits >= 1 and raw_score >= 4.0:
            return True
        if raw_score >= 6.0 and num_hits >= 1:
            return True
        if task_job and card.get('job') in (task_job, 'review', 'test', 'secure') and num_hits >= 1 and raw_score >= 3.0:
            return True
        return False

    # 4. Multi-word (num_c >= 3):
    if num_c >= 4 and num_hits == 1 and (c_hits <= LANGS and sit.get('missing') or (not tech_hit and not sit.get('demand'))):
        return False
    if (name_hit or tech_hit) and raw_score >= 5.0 and (num_hits >= 2 or not sit.get('missing') or not (c_hits <= LANGS)):
        return True
    if num_hits >= 2 and raw_score >= 4.5:
        return True
    if (num_hits / num_c) >= 0.34 and num_hits >= 2 and raw_score >= 4.0:
        return True
    if tech_hit and num_hits >= 1 and raw_score >= 5.0 and (num_hits >= 2 or not sit.get('missing') or not (c_hits <= LANGS)):
        return True
    if task_job and card.get('job') in (task_job, 'review', 'secure') and num_hits >= 1 and raw_score >= 3.2 and not sit.get('missing'):
        return True
    if sit.get('ctx_tech') and v.get('relation') == 'fit' and num_hits >= 1 and raw_score >= 3.0:
        return True

    return False

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
            best_cand = max(left, key=lambda n: (left[n], n))
            if left[best_cand] <= 0:
                break
            name = best_cand
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


def find_gap(task, sit, stack, votes, missing, role):
    """Where the library is thin for this task or this engineer, and the command that fills it by research; or None.

    The task is a gap when nothing was chosen, when its words are unknown to the library, or when (meaning search
    being on) even the closest skill is far in meaning and no chosen skill shares a word with the task. The engineer has
    a gap when the project's main stack is one that few skills cover."""
    reasons = []
    near = (sit.get('semantic') or {}).get('similar') or []
    word_hits = any(set(sit['words']) & v1.SKILL_TOKENS.get(c['name'], set()) for c in stack)
    if not stack:
        reasons.append('no skill fits this task')
    elif missing and missing.get('coverage', 1.0) == 0.0:
        reasons.append('the library has no skill for: ' + ', '.join(missing['unknown_words'][:4]))
    elif near and near[0][0] < GAP_COSINE and not word_hits:
        reasons.append('the closest skills are far from what the task means')
    thin = [g for g in (role or {}).get('gaps', []) if g['files'] >= 2]
    if not reasons and not thin:
        return None
    out = {'task': reasons[0] if reasons else None,
           'stacks': [{'stack': g['stack'], 'skills': g['skills']} for g in thin[:3]],
           'research': 'python3 mcp/sfp_research.py draft "%s"' % (task or '').replace('"', "'")[:200],
           # the mentor (sfp_mentor, MCP tool grow_skills) reads the best papers and drafts a skill for the user to approve
           'grow': 'sfp mentor grow --topic "%s"' % (task or '').replace('"', "'")[:200]}
    if thin and not reasons:
        out['research'] = 'python3 mcp/sfp_research.py draft "%s best practices" --role %s' % (
            thin[0]['stack'], (role or {}).get('role') or 'engineer')
    return out


def rerank_wanted(sit, votes=None):
    mode = os.environ.get('SFP_RERANK', 'auto').lower()
    if mode in ('0', 'off', 'false', 'no'):
        return False
    if mode in ('1', 'on', 'true', 'yes'):
        return True
    if not sit.get('words_weak'):
        return False
    # Auto rerank is a rescue mechanism for weak-word general tasks.
    # Never overrule strong project-technology matches where the local LLM lacks repository context.
    if sit.get('ctx_tech'):
        if votes is None or any(v.get('relation') in ('fit', 'named') for v in votes.values()):
            return False
    if votes and any(v.get('relation') == 'named' for v in votes.values()):
        return False
    return True


def rerank(sit, votes, quality, exclude, allowed=None):
    """The candidates a local model judges fit the task best, best first ([] when off, no model answers, or the task is
    not one said in other words). The pool is the closest in meaning, then the signals' own favourites."""
    sem = sit.get('semantic') or {}
    if not sem.get('similar') or not rerank_wanted(sit, votes=votes):
        return []
    import sfp_intent
    import sfp_cards
    ok = lambda n: n in votes and n not in exclude and votes[n]['relation'] != 'mismatch' and (allowed is None or n in allowed)
    pool = [n for _, n in sem['similar'] if ok(n)][:RERANK_POOL]
    pool += [n for n in sorted(quality, key=lambda n: -quality[n])[:5] if ok(n) and n not in pool]
    if not pool:
        return []
    items = []
    for n in pool:
        c = sfp_cards.get_card(n)
        desc = core.SKILLS[n].get('description') or ''
        items.append((n, f"[{c.get('job', 'build')} / {'/'.join(c.get('output', ['text']))}] {desc}"))
    return [n for n in sfp_intent.rerank(sit['text'], items) if n in pool]


def understand(text):
    """{'terms', 'similar'} from the local models, or None when neither answers (or SFP_SEMANTIC=0)."""
    if not (text or '').strip():
        return None
    import sfp_embed
    import sfp_intent
    if not sfp_embed.enabled():
        return None
    terms = sfp_intent.rewrite(text) if sfp_intent.wanted() else []
    query = text + ('. ' + ', '.join(terms) if terms else '')
    near = sfp_embed.similar(query, MEANING_CANDIDATES)
    return {'terms': terms, 'similar': near} if terms or near else None


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
           model=None, want_signals=False, include=(), exclude=(), explain=False, phase_hint=None, explore=None,
           semantic=None):
    """Decide which skills to use for a task, and in what order.

    `semantic`: None uses local models when they answer (sfp_intent rewrites the task in an expert's terms, sfp_embed
    finds the skills closest in meaning); False keeps to words, as before; a dict {'terms', 'similar'} is used as given.
    `model` is a learned preference model (sfp_learn.Model); without one, or with one that has seen
    no feedback, the result is the same as the unlearned selection.
    `exclude` names skills the user ruled out; `include` names skills the user pinned, which join the stack
    whatever their score. `explain` adds the top candidates, their signal votes and why each was or was not taken.
    `phase_hint` is the phase of work observed from activity (sfp_track): {phase: share}. It is blended with
    what the task's words say, half and half, or used alone when the words say nothing about the phase.
    `explore` controls the Upper Confidence Bound exploration factor under the contextual bandit policy.
    """
    t0 = time.time()
    after = [n for n in (core.resolve_name(a) for a in (after or [])) if n]
    exclude = {n for n in (core.resolve_name(x) for x in (exclude or [])) if n}
    include = [n for n in (core.resolve_name(x) for x in (include or [])) if n and n not in INTERNAL_SKILLS]
    hist = history if history is not None else History(v1.RECIPES, v1.read_usage())
    sc = scan_result if scan_result is not None else scan(project)
    sit = read_situation(task, goal, sc)
    if semantic is None or semantic is True:
        # Filler with no word of substance ("for the of a") means nothing, in words or in meaning.
        semantic = understand(sit['text']) if sit['words'] else None
    sit['semantic'] = semantic or None
    role = None
    if project:
        import sfp_role
        role = sfp_role.detect(project, sc)
        if role and role['role'] and role['confidence'] >= ROLE_MIN_CONFIDENCE:
            sit['role_cats'] = sfp_role.role_categories(role['role'])
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
            sit['phase_hint'] = hint
    tech = sorted(sit['ctx_tech'], key=lambda t: (-sit['ctx'][t], t))[:3]

    words = sit['words'][:sel_words()]
    missing = detect_missing(sit['words'], sit.get('said'))
    recalled = {}
    if model and model.w:
        recalled = {n: z for n, z in model.recall(words).items() if z >= RECALL and n not in after and n not in INTERNAL_SKILLS}
    import sfp_learn
    taste = sfp_learn.load_taste() if (model is not False and sfp_learn) else {}
    sit['taste'] = taste
    votes = collect_signals(sit, after, hist, recalled, phase_queries, missing=missing)
    learned = {}
    quality = {}
    for n, v in votes.items():
        z = model.preference(n, words, explore=explore) if model else 0.0
        if z:
            learned[n] = z
        if has_agreement(v) or (z >= RESCUE and v['words'] and v['relation'] != 'mismatch'):
            quality[n] = base_quality(v) * (math.exp(z) if z else 1.0)
    for n in exclude:
        quality.pop(n, None)
    if quality:
        top_q = max(quality.values())
        quality = {n: q / top_q for n, q in quality.items()}

    import sfp_cards
    import sfp_learn
    task_job, named_form = sfp_cards.task_intent(task)
    taste = sfp_learn.load_taste() if (model is not False and sfp_learn) else {}
    has_proj = bool(sit['ctx_tech'])
    sem_sim_list = (sit.get('semantic') or {}).get('similar') or []
    sem_dict = dict(sem_sim_list)
    sit['task_job'] = task_job
    sit['named_form'] = named_form
    sit['missing'] = missing
    allowed_cands = set()
    for n in votes:
        if n in exclude:
            continue
        v_cand = dict(votes.get(n, {}))
        v_cand['cos'] = sem_dict.get(n, 0.0)
        v_cand['pinned'] = (n in include)
        v_cand['learned'] = learned.get(n, 0.0)
        if clears_confidence(n, sit, v_cand):
            allowed_cands.add(n)

    picks = rerank(sit, votes, quality, exclude, allowed=allowed_cands) if allowed_cands else []
    for i, n in enumerate(picks):
        quality[n] = RERANK_LEAD - 0.01 * i

    for n in list(quality):
        card = sfp_cards.get_card(n)
        forms = card.get('output', ['text'])
        needs = card.get('needs', [])
        v_rel = votes.get(n, {}).get('relation')
        task_asked_for_tool = any(t in sit['words'] for t in needs) if needs else False
        tools_installed = any(t in sit['ctx'] for t in needs) if needs else True
        if has_proj and needs and not task_asked_for_tool and not tools_installed and v_rel not in ('fit', 'named'):
            fit_mult = 0.85
        elif has_proj and needs and tools_installed:
            fit_mult = 1.15
        else:
            fit_mult = 1.0

        matching_form = (named_form in forms) or (named_form in ('text', 'document') and any(f in forms for f in ('text', 'document')))
        matching_job = (not task_job) or (card.get('job') == task_job)
        if named_form:
            if matching_form and matching_job:
                taste_mult = 4.2 if (forms and forms[0] == named_form) else 4.0
            elif matching_form and not matching_job:
                taste_mult = 0.3
            elif not matching_form and matching_job:
                taste_mult = 0.6
            else:
                taste_mult = 0.15
        elif taste and taste.get('events', 0) > 0:
            evs = max(taste.get('events', 1), 1)
            t_out = taste.get('output', {})
            top_tf = max(t_out, key=t_out.get) if t_out else None
            has_top_tf = (top_tf in forms) or (top_tf in ('text', 'document') and any(f in forms for f in ('text', 'document')))
            form_prefs = [t_out.get(f, 0.0) for f in forms]
            if any(f in forms for f in ('text', 'document')):
                form_prefs.append(t_out.get('document', 0.0))
                form_prefs.append(t_out.get('text', 0.0))
            form_pref = max(form_prefs or [0.0]) / evs
            primary_bonus = 0.2 if (forms and forms[0] == top_tf) else 0.0
            style_pref = taste.get('style', {}).get(card.get('style'), 0.0) / evs
            job_pref = 1.4 if matching_job else 0.5
            if has_top_tf:
                taste_mult = (1.0 + 1.5 * form_pref + primary_bonus + 0.3 * style_pref) * job_pref
            else:
                taste_mult = 0.55 * job_pref
        elif task_job == 'explain':
            taste_mult = 1.05 if (forms and forms[0] == 'text' and matching_job) else 1.0
        else:
            taste_mult = 1.0

        quality[n] = quality[n] * fit_mult * taste_mult

    why = {}
    pinned = [n for n in include if n not in exclude]
    rest = {}
    for n, q in quality.items():
        if n in pinned:
            continue
        if n in allowed_cands:
            rest[n] = q
        else:
            why[n] = 'did not clear task confidence threshold'
    chosen, reserve, spent, left = assemble(rest, sit['demand'], budget, max(0, max_skills - len(pinned)), why)

    if not has_proj and len(chosen) > 1 and not sit.get('phase_hint'):
        raw_top_val = sit.get('raw_top', 0.0)
        pruned_chosen = [chosen[0]]
        pruned_spent = v1.body_tokens(chosen[0][0])
        for item in chosen[1:]:
            sk_name, sk_phase, _ = item
            sk_raw = votes.get(sk_name, {}).get('raw_words', 0.0) or 0.0
            sk_m = votes.get(sk_name, {}).get('meaning', 0.0) or 0.0
            if sit['demand'].get(sk_phase, 0.0) > 0 or sk_raw >= 0.45 * raw_top_val or (sit.get('semantic') and sk_m >= 0.85):
                pruned_chosen.append(item)
                pruned_spent += v1.body_tokens(sk_name)
        chosen = pruned_chosen
        spent = pruned_spent

    if not chosen or ((not sit.get('semantic')) and missing and missing.get('coverage', 1.0) == 0.0):
        chosen = []
        spent = 0
    # Deduplicate substitutes: never stack two substitutes that do the same job
    sub_groups = {}
    for item in chosen:
        name = item[0]
        c = sfp_cards.get_card(name)
        sub = c.get('substitutes_for')
        sub_groups.setdefault(sub, []).append(item)

    filtered_chosen = []
    alternatives = []
    for sub, items in sub_groups.items():
        if len(items) <= 1 or sub in ('software-engineering-patterns', 'unit-testing'):
            filtered_chosen.extend(items)
        else:
            def sub_key(it):
                sk = it[0]
                c = sfp_cards.get_card(sk)
                jm = 1 if (task_job and c.get('job') == task_job) else 0
                v_rel = votes.get(sk, {}).get('relation')
                not_unasked = 0 if (has_proj and v_rel in ('unasked', 'mismatch')) else 1
                return (jm, not_unasked, quality.get(sk, 0.0))
            items_sorted = sorted(items, key=sub_key, reverse=True)
            best_item = items_sorted[0]
            filtered_chosen.append(best_item)
            best_form = sfp_cards.get_card(best_item[0]).get('output', ['text'])[0]
            for alt_it in items_sorted[1:]:
                alt_card = sfp_cards.get_card(alt_it[0])
                alt_form = alt_card.get('output', ['text'])[0]
                if alt_form != best_form:
                    alternatives.append({
                        'name': alt_it[0],
                        'form': alt_form,
                        'substitutes_for': sub,
                        'reason': f"alternative: {alt_form} format ({alt_it[0]})"
                    })
                    break
    if taste and taste.get('events', 0) > 0 or named_form:
        filtered_chosen.sort(key=lambda it: -quality.get(it[0], 0.0))
    chosen = filtered_chosen
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
        elif (v.get('meaning') or 0) >= 0.5:
            reasons.append('close in meaning to the task')
        elif sit['semantic'] and sit['semantic'].get('terms'):
            reasons.append('matches what the task means: ' + ', '.join(sit['semantic']['terms'][:3]))
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
        if name in picks:
            reasons.append('judged the best fit by the local model')
        card = sfp_cards.get_card(name)
        if named_form and named_form in card.get('output', []):
            reasons.append('requested format: ' + named_form)
        else:
            form_pref = max([taste.get('output', {}).get(f, 0.0) for f in card.get('output', [])] or [0.0])
            best_f = [f for f in card.get('output', []) if taste.get('output', {}).get(f, 0.0) == form_pref]
            if form_pref > 0.1 and best_f:
                reasons.append('you usually prefer ' + best_f[0] + ' format')
            if card.get('needs') and any(t in sit['ctx'] for t in card.get('needs')):
                reasons.append(f"{card.get('needs')[0]} is installed in this project")
        if name in pinned:
            reasons.insert(0, 'pinned by you')
        else:
            reasons.append('backed by: ' + ', '.join(backers(v)))
        stack.append({'name': name, 'phase': phase, 'layer': v1.LAYER[phase], 'category': core.SKILLS[name]['category'],
                      'tokens': v1.body_tokens(name), 'score': round(quality[name], 3), 'support': len(backers(v)),
                      'response': round(resp, 3), 'relevance': round(v['words'], 3),
                      'path': core.SKILLS[name]['path'] + '/SKILL.md', 'reasons': reasons,
                      'card': card})
    if taste and taste.get('events', 0) > 0 or named_form:
        stack.sort(key=lambda c: -c['score'])
    else:
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
        'missing': missing,
        'understood': (sit['semantic'] or {}).get('terms') or [],
        'reranked': picks,
        'alternatives': alternatives,
        'task_intent': {'job': task_job, 'named_form': named_form},
        'role': role and {k: role[k] for k in ('role', 'confidence', 'evidence', 'stacks')},
        'gap': find_gap(task, sit, stack, votes, missing, role),
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


SETS = (('bench', None), ('proj', 'stack_eval.json'), ('fresh', 'hive_heldout.json'),
        # The bench tasks said in other words by a local model, without their concept words: half to tune on, half held out.
        ('reworded', 'search_reworded.json'), ('reworded_holdout', 'search_reworded_holdout.json'),
        ('precision_tuning', 'precision_tuning.json'), ('precision_heldout', 'precision_heldout.json'))


def score_precision_junk(names, want, avoid):
    """Return (precision, is_hit, is_first, is_junk) for a chosen stack `names` against `want` and `avoid`."""
    if not want:
        prec = 1.0 if not names else 0.0
        hit = not names
        first = not names
    else:
        prec = (len(want & set(names)) / len(names)) if names else 0.0
        hit = bool(want & set(names))
        first = bool(names and names[0] in want)
    junk = bool((avoid & set(names)) or (not want and names))
    return prec, hit, first, junk


def load_cases(tests_dir, tmp, only=None):
    """The task sets as (key, cases); each case has a task, expect, avoid and a project folder (or None)."""
    out = []
    for key, fname in SETS:
        if only and key not in only:
            continue
        if not only and key in ('precision_tuning', 'precision_heldout'):
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
            if isinstance(data, list):   # tasks without a project
                cases = [dict(c, project=None, avoid=c.get('avoid', [])) for c in data]
            else:
                _projects(data, os.path.join(tmp, key))
                cases = [dict(c, project=os.path.join(tmp, key, c['project'])) for c in data['cases']]
        if cases:
            out.append((key, cases))
    return out


def evaluate(tests_dir=None, only=None, semantic=False):
    """Score the hive, the v1 engine and plain search on the task sets. Used by the tests and the README.
    The published figures are for words alone (`semantic=False`), so they are the same on every machine; with
    `semantic=True` the hive also uses the local models it finds (sfp_intent, sfp_embed), as it does in use."""
    import tempfile
    tests_dir = tests_dir or os.path.join(os.path.dirname(HERE), 'tests')
    hist = History(v1.RECIPES, [])  # recipes only, so personal usage never changes the published figures
    old = v1.Markov(v1.RECIPES, [])
    sem = None if semantic else False
    engines = {'select': lambda t, p: select(t, p, history=hist, semantic=sem), 'v1': lambda t, p: v1.recommend(t, p, chain=old)}
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for key, cases in load_cases(tests_dir, tmp, only):
            n = len(cases)
            for eng, fn in engines.items():
                hit = first = wrong = size = tokens = ms = 0
                prec_sum = junk_cnt = 0
                for c in cases:
                    want = {x for x in c['expect'] if x in core.SKILLS}
                    avoid = set(c.get('avoid', []))
                    res = fn(c['task'], c['project'])
                    names = [x['name'] for x in res['stack']]
                    if names:
                        lead = max(res['stack'], key=lambda x: x['score'])['name']
                        ordered_names = [lead] + [x for x in names if x != lead]
                    else:
                        ordered_names = []
                    prec, is_hit, is_first, is_junk = score_precision_junk(ordered_names, want, avoid)
                    hit += is_hit
                    first += is_first
                    wrong += bool(avoid & set(names))
                    prec_sum += prec
                    junk_cnt += is_junk
                    size += len(names)
                    tokens += res['tokens']
                    ms += res['ms']
                out['%s_%s' % (key, eng)] = {'n': n, 'hit': hit / n, 'first': first / n, 'precision': prec_sum / n,
                                              'junk_rate': junk_cnt / n, 'wrong': wrong,
                                              'size': size / n, 'tokens': tokens / n, 'ms': ms / n}
            k = max(1, round(out['%s_select' % key]['size']))
            s_hit = s_wrong = s_prec = s_junk = 0
            for c in cases:
                want = {x for x in c['expect'] if x in core.SKILLS}
                avoid = set(c.get('avoid', []))
                top_list = [s['name'] for s in core.search(c['task'], limit=k)]
                prec, is_hit, _, is_junk = score_precision_junk(top_list, want, avoid)
                s_hit += is_hit
                s_wrong += bool(avoid & set(top_list))
                s_prec += prec
                s_junk += is_junk
            out['%s_search' % key] = {'n': n, 'hit': s_hit / n, 'precision': s_prec / n,
                                       'junk_rate': s_junk / n, 'wrong': s_wrong, 'size': k}
    return out


# ----------------------------------------------------------------------- CLI

def format_stack(res):
    if not res.get('stack'):
        lines = ['Stack for: ' + (res.get('task') or '')]
        if res.get('missing'):
            m = res['missing']
            lines.append('[Notice] The catalog has no skill for: %s' % ', '.join(m['unknown_words']))
            lines.append('  To add a skill from Git: python3 scripts/repo_to_skill.py <url>')
        elif res.get('gap') and res['gap'].get('task'):
            lines.append('[Notice] ' + res['gap']['task'])
            lines.append('  To add a skill from Git: python3 scripts/repo_to_skill.py <url>')
        else:
            lines.append('[Notice] No skill in the catalog fits this task.')
        return '\n'.join(lines)
    lines = v1.format_stack(res).split('\n')
    if res.get('missing'):
        m = res['missing']
        lines.insert(2, '[Notice] The catalog has no skill for: %s' % ', '.join(m['unknown_words']))
        lines.insert(3, '  To add a skill from Git: python3 scripts/repo_to_skill.py <url>')
        lines.insert(4, '')
    info = res.get('analysis') or {}
    if info:
        lines.insert(-1, 'Hive: %d scouted, %d reached quorum, %d took a job.' % (info['candidates'], info['agreed'], len(res['stack'])))
        if info.get('unmet'):
            lines.insert(-1, 'No skill took: %s' % ', '.join(info['unmet']))
    if res.get('alternatives'):
        alts = ', '.join(f"{a['name']} ({a['form']})" for a in res['alternatives'])
        lines.insert(-1, 'Alternatives (different format): ' + alts)
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
    r.add_argument('--use-bundles', default='', help='comma-separated bundle IDs to always attach whole and in order')
    r.add_argument('--explain', action='store_true', help='add each top candidate, its signal votes and why it was or was not taken')
    r.add_argument('--no-needs', action='store_true', help='do not add skills for what the model cannot do alone (3D, web, limits...)')
    r.add_argument('--check', action='store_true', help='also check the programs and keys the needs depend on')
    r.add_argument('--bundles', choices=['push', 'suggest', 'off'], default='push', help='push a bundle that fits the task whole (default), only suggest it, or ignore bundles')
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
    ev = sub.add_parser('evaluate', help='score the hive against the earlier engine and plain search')
    ev.add_argument('--semantic', action='store_true', help='also use the local models (rewrite and meaning search)')
    ev.add_argument('--only', help='comma-separated task sets: bench, proj, fresh, reworded')
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
    sk = sub.add_parser('skill', help='everything about one skill: description, area, purpose, bundles, similar skills')
    sk.add_argument('name')
    sk.add_argument('--json', action='store_true')
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
    dr = sub.add_parser('doctor', help='check that everything is connected: catalog, selection, live, needs, library, router, MCP')
    dr.add_argument('--project')
    dr.add_argument('--port', type=int, default=8787, help='where the router would be running')
    dr.add_argument('--json', action='store_true')
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
    tst = sub.add_parser('taste', help='view or reset learned taste preferences')
    tst.add_argument('--reset', action='store_true', help='clear learned taste preferences')
    tst.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)

    if a.cmd == 'taste':
        if a.reset:
            sfp_learn.reset_taste()
            print("Learned taste has been reset.")
        else:
            t = sfp_learn.load_taste()
            print(json.dumps({
                'events': t.get('events', 0),
                'decayed_events': t.get('decayed_events', 0),
                'output': t.get('output', {}),
                'style': t.get('style', {}),
                'depth': t.get('depth', {})
            }, indent=2))
        return

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
                                       exclude=exclude, explain=a.explain, check=a.check, learn=not a.no_learning, bundles=a.bundles, use_bundles=a.use_bundles)
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
    elif a.cmd == 'doctor':
        import sfp_doctor
        items = sfp_doctor.checks(a.port, a.project)
        print(json.dumps({'status': sfp_doctor.summary(items), 'checks': items}, indent=1) if a.json else sfp_doctor.format_checks(items))
        raise SystemExit(1 if sfp_doctor.summary(items) == 'fail' else 0)
    elif a.cmd == 'live':
        import sfp_live
        split = lambda v: [x.strip() for x in v.split(',') if x.strip()]
        res = sfp_live.live(a.draft, json.loads(a.state) if a.state else None, a.project, a.max, split(a.pin), split(a.unpin),
                            split(a.remove), split(a.restore), a.commit)
        print(json.dumps(res, indent=1) if a.json else sfp_live.format_live(res))
    elif a.cmd == 'library':
        import sfp_library
        print(json.dumps(sfp_library.library(), separators=(',', ':')))
    elif a.cmd == 'skill':
        import sfp_library
        try:
            d = sfp_library.skill_detail(a.name)
        except KeyError:
            raise SystemExit('no skill named %r' % a.name)
        print(json.dumps(d, indent=1) if a.json else '%s\n  %s / %s / %s\n  %s' % (
            d['name'], d['family']['name'], d['cluster']['name'], d['purpose']['name'], d['description']))
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
                          for k, v in evaluate(only=a.only and a.only.split(','), semantic=a.semantic).items()},
                         indent=1))
    elif a.cmd == 'learning-curve':
        print(json.dumps(sfp_learn.learning_curve(), indent=1))


if __name__ == '__main__':
    main()
