#!/usr/bin/env python3
"""Feedback and learning for SFP skill selection.

The hive (sfp_hive.py) makes a decision: a few skills, in order. This module closes the loop.

  1. Every decision is logged: the skills chosen, what each signal voted for the strongest candidates,
     the project's main technologies, and the stems of the task's main words (for example `test`,
     `order`, `view`). No sentences, no file contents and no paths.
  2. You, or the agent on your behalf, give feedback on a decision: which skills helped, which did
     not, which were chosen but never used, and which should have been chosen.
  3. A small model learns from that feedback and adjusts future selections.

What it learns is which words go with which skills. The model is a regularised logistic regression whose
features are pairs (word stem, skill), valued higher for rarer words. It predicts whether the skill
helps for a task containing those words. Its output for a skill, z, scales the skill's quality by exp(z),
and a strong association also brings in a skill the keyword search missed. With no feedback every weight
is zero, so z is zero and the selection is exactly the unlearned one.

Why words, not skills. Whether a skill helps depends on the task. An earlier design that learned a global
weight per skill, per technology and per signal made held-out selection worse on the benchmark (see
docs/HIVE.md): a skill that helped on three tasks was wrongly favoured on a fourth. Word-conditional
memory fixes the reported mistake and the tasks that look like it, and leaves unrelated tasks alone.

Mistakes teach the most. A skill reported unhelpful, or a skill reported missing, produces a large error
and so a large update. A skill that was chosen but never used counts for a third as much, because not
being used is weaker evidence than being unhelpful. Strong regularisation means one report moves a skill
for that kind of task and no single report can ban it. Feedback loses weight with a half-life of 120
days. Every skill's change is clamped, so a skill's quality moves by at most about 3.3 times.

Files, in the data folder (~/.sfp, or the folder of $SFP_USAGE_LOG)
  decisions.jsonl   one line per decision: id, time, technologies, word stems, chosen skills, votes
  feedback.jsonl    one line per verdict: decision id, skill, verdict, time
Set SFP_LEARN_WORDS=0 to stop recording word stems (feedback then only affects statistics and the
history signal). Set SFP_NO_LEARNING=1 (or SFP_NO_USAGE_LOG=1) to record and learn nothing. `forget`
deletes it all. Standard library only; nothing leaves the machine.
"""
import json
import math
import os
import secrets
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import sfp_mcp as core  # noqa: E402
import sfp_stack as v1  # noqa: E402
import sfp_hive as sel  # noqa: E402

VERDICTS = ('helped', 'unhelpful', 'ignored', 'missing')
WORDS_PER_DECISION = 12
# How much each verdict counts as a training example, and its label (1 = the skill should be chosen).
VERDICT_WEIGHT = {'helped': 1.0, 'unhelpful': 1.0, 'missing': 1.0, 'ignored': 0.3}
VERDICT_LABEL = {'helped': 1, 'unhelpful': 0, 'missing': 1, 'ignored': 0}
HALF_LIFE_FEEDBACK_DAYS = 120.0
REGULARISE = 1.0               # L2 strength on every weight: the larger, the more reports it takes to move a skill
MAX_PREFERENCE = 1.2           # |z| is clamped here: a skill's quality changes by at most about 3.3x
FIT_ITERATIONS = 60
MAX_DECISIONS = 3000           # older decisions are dropped when the file grows past 1.5x this
MAX_FEEDBACK_AGE_DAYS = 365


# ------------------------------------------------------------------- storage

def data_dir():
    return os.environ.get('SFP_DATA_DIR') or os.path.dirname(v1.usage_path())


def enabled():
    return not (os.environ.get('SFP_NO_LEARNING') or os.environ.get('SFP_NO_USAGE_LOG'))


def _path(name):
    return os.path.join(data_dir(), name)


def _stat(path):
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _read_lines(path):
    out = []
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict):
                    out.append(e)
    except OSError:
        pass
    return out


def _append(name, record):
    os.makedirs(data_dir(), exist_ok=True)
    with open(_path(name), 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, separators=(',', ':')) + '\n')


def _compact_decisions():
    path = _path('decisions.jsonl')
    rows = _read_lines(path)
    if len(rows) <= int(MAX_DECISIONS * 1.5):
        return
    keep = rows[-MAX_DECISIONS:]
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for r in keep:
            f.write(json.dumps(r, separators=(',', ':')) + '\n')
    os.replace(tmp, path)


def load_decisions():
    """Decisions by id, newest last. Lines with an unknown shape are ignored."""
    out = {}
    for r in _read_lines(_path('decisions.jsonl')):
        if isinstance(r.get('id'), str) and isinstance(r.get('stack'), list):
            out[r['id']] = r
    return out


def load_feedback():
    """Feedback lines that name a real skill and a known verdict, oldest first."""
    out = []
    for r in _read_lines(_path('feedback.jsonl')):
        if r.get('verdict') in VERDICTS and r.get('skill') in core.SKILLS:
            out.append(r)
    return out


# --------------------------------------------------------------------- model

def _rarity(word):
    """How informative a word is: 1.0 for a word in few skills, less for a common one."""
    n = len(core.SKILLS)
    unseen = math.log(1 + n)
    return min(1.0, 1.5 * math.log(1 + n / (1 + core.DF.get(word, 0))) / unseen)


def features(skill, words):
    """The numbers the model sees for one skill and one task: one feature per task word."""
    return {'%s|%s' % (w, skill): _rarity(w) for w in (words or ())[:WORDS_PER_DECISION]}


class Model:
    """Regularised logistic regression from (word, skill) pairs to 'this skill helped'. Zero weights mean no opinion."""

    def __init__(self, weights=None, examples=0):
        self.w = dict(weights or {})
        self.examples = examples
        self._by_word = None

    def preference(self, skill, words):
        """The bounded log-scale change to the skill's quality: 0 for a model that has learned nothing."""
        if not self.w:
            return 0.0
        z = sum(self.w.get(f, 0.0) * x for f, x in features(skill, words).items())
        return max(-MAX_PREFERENCE, min(MAX_PREFERENCE, z))

    def recall(self, words):
        """Skills the model has tied to these words, with their preference: how it finds what search missed."""
        if self._by_word is None:
            self._by_word = {}
            for f in self.w:
                word, skill = f.split('|', 1)
                self._by_word.setdefault(word, []).append(skill)
        out = {}
        for w in (words or ())[:WORDS_PER_DECISION]:
            for skill in self._by_word.get(w, ()):
                if skill not in out:
                    z = self.preference(skill, words)
                    if z > 0:
                        out[skill] = z
        return out


def _sigmoid(z):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def fit(examples):
    """Fit the model to examples [(features, label, weight)] by damped diagonal Newton steps.

    Minimises  sum_i weight_i * logloss_i  +  sum_f 0.5 * lambda * w_f^2  with no bias term, so a
    skill is judged against a neutral prior of 0.5, not against how often feedback is positive.
    """
    names = set()
    for x, _, _ in examples:
        names.update(x)
    w = {f: 0.0 for f in names}
    for _ in range(FIT_ITERATIONS):
        grad = {f: 0.0 for f in names}
        hess = {f: 0.0 for f in names}
        for x, y, weight in examples:
            p = _sigmoid(sum(w[f] * v for f, v in x.items()))
            for f, v in x.items():
                grad[f] += weight * (p - y) * v
                hess[f] += weight * 0.25 * v * v
        biggest = 0.0
        for f in names:
            step = 0.6 * (grad[f] + REGULARISE * w[f]) / (hess[f] + REGULARISE)
            w[f] -= step
            biggest = max(biggest, abs(step))
        if biggest < 1e-5:
            break
    return Model({f: round(v, 6) for f, v in w.items() if abs(v) > 1e-6}, len(examples))


def build_examples(decisions, feedback, now=None):
    """Turn feedback into training examples. The latest verdict for a (decision, skill) pair wins."""
    now = now or time.time()
    latest = {}
    for r in feedback:
        latest[(r.get('decision'), r['skill'])] = r
    examples = []
    for (did, skill), r in latest.items():
        age = max(0.0, now - r.get('t', now)) / 86400.0
        if age > MAX_FEEDBACK_AGE_DAYS:
            continue
        words = r.get('words') or (decisions.get(did) or {}).get('words') or []
        if not words:
            continue        # without the task's words there is nothing to condition on
        decay = 2.0 ** (-age / HALF_LIFE_FEEDBACK_DAYS)
        examples.append((features(skill, words), VERDICT_LABEL[r['verdict']], VERDICT_WEIGHT[r['verdict']] * decay))
    return examples


_CACHE = {}


def _cached(key, stamp, build):
    hit = _CACHE.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    val = build()
    _CACHE[key] = (stamp, val)
    return val


def _stamp():
    return (data_dir(), _stat(_path('decisions.jsonl')), _stat(_path('feedback.jsonl')), _stat(v1.usage_path()))


def load_model():
    if not enabled():
        return Model()

    def build():
        return fit(build_examples(load_decisions(), load_feedback()))
    return _cached('model', _stamp(), build)


def history_events(decisions=None, feedback=None):
    """Sequences of skills for the history signal: recorded usage, plus the stack of every decision that helped."""
    events = list(v1.read_usage())
    decisions = decisions if decisions is not None else load_decisions()
    feedback = feedback if feedback is not None else load_feedback()
    helped = {r.get('decision') for r in feedback if r['verdict'] == 'helped'}
    for did in helped:
        d = decisions.get(did)
        if d:
            for name in d['stack']:
                if name in core.SKILLS:
                    events.append({'t': d.get('t', 0), 'skill': name, 'session': did})
    for r in feedback:
        if r.get('verdict') == 'missing' and r.get('decision') in decisions:
            did = r['decision']
            d = decisions[did]
            if r.get('skill') in core.SKILLS:
                events.append({'t': r.get('t', d.get('t', 0)), 'skill': r['skill'], 'session': did})
    return events


def load_history():
    if not enabled():
        return sel.History(v1.RECIPES, [])

    def build():
        return sel.History(v1.RECIPES, history_events())
    return _cached('history', _stamp(), build)


# ----------------------------------------------------------------- decisions

def keep_words():
    return os.environ.get('SFP_LEARN_WORDS', '1') not in ('0', 'false', 'no')


def decide(task, project=None, goal=None, after=(), budget=12000, max_skills=4, learn=True, include=(), exclude=(), explain=False):
    """Select skills, apply what has been learned, and log the decision so feedback can refer to it."""
    use = learn and enabled()
    res = sel.select(task, project, goal, after, budget, max_skills,
                     history=load_history(), model=load_model() if use else None, want_signals=True,
                     include=include, exclude=exclude, explain=explain)
    record = res.pop('_record')
    res['learning'] = {'enabled': use, 'examples': load_model().examples if use else 0, 'words_kept': keep_words()}
    res['decision'] = None
    if enabled():
        did = 'd_' + secrets.token_hex(4)
        row = {'id': did, 't': int(time.time()), 'v': 3, 'engine': sel.VERSION, 'tech': record['tech'],
               'phases': record['phases'], 'stack': [c['name'] for c in res['stack']], 'cand': record['candidates']}
        if keep_words():
            row['words'] = record['words']
        _append('decisions.jsonl', row)
        _compact_decisions()
        res['decision'] = did
        res['feedback'] = ('After the task, call give_feedback with this decision id: helped, unhelpful, '
                           'ignored (chosen but never used) and missing (should have been chosen).')
    return res


def last_decision_id():
    rows = _read_lines(_path('decisions.jsonl'))
    for r in reversed(rows):
        if isinstance(r.get('id'), str):
            return r['id']
    return None


def _names(skills, what):
    out = []
    for s in skills or ():
        n = core.resolve_name(s)
        if not n:
            near = [x['name'] for x in core.search(s, limit=3)]
            raise ValueError('no skill named %r (%s).%s' % (s, what, (' Closest: %s.' % ', '.join(near)) if near else ''))
        out.append(n)
    return list(dict.fromkeys(out))


def give_feedback(decision=None, helped=(), unhelpful=(), ignored=(), missing=(), task=None):
    """Record what happened to a decision. Returns what was recorded and how the model's view of each skill moved.

    `task` is only needed when the decision did not keep the task's words (SFP_LEARN_WORDS=0), or for
    feedback on a task the hive never decided; the words are then stored with the feedback.
    """
    if not enabled():
        return {'recorded': 0, 'reason': 'learning is turned off (SFP_NO_LEARNING or SFP_NO_USAGE_LOG)'}
    groups = {'helped': _names(helped, 'helped'), 'unhelpful': _names(unhelpful, 'unhelpful'),
              'ignored': _names(ignored, 'ignored'), 'missing': _names(missing, 'missing')}
    if not any(groups.values()):
        raise ValueError('say which skills helped, did not help, were ignored or were missing')
    if decision in ('last', 'latest'):
        decision = last_decision_id()
    d = None
    if decision:
        d = load_decisions().get(decision)
        if d is None:
            raise ValueError('no decision %r. Use the id that select_skills returned, or "last".' % decision)
    seen = {}
    for verdict, names in groups.items():
        for n in names:
            if n in seen and seen[n] != verdict:
                raise ValueError('%s is listed as both %s and %s' % (n, seen[n], verdict))
            seen[n] = verdict
    words = (d or {}).get('words') or []
    own_words = []
    if not words and task and keep_words():
        own_words = v1.task_words(task)[:WORDS_PER_DECISION]
        words = own_words
    before = load_model()
    now = int(time.time())
    for verdict, names in groups.items():
        for n in names:
            row = {'t': now, 'decision': decision, 'skill': n, 'verdict': verdict}
            if own_words:
                row['words'] = own_words
            _append('feedback.jsonl', row)
    after = load_model()
    out = {'recorded': sum(len(v) for v in groups.values()), 'decision': decision, 'examples': after.examples,
           'moved': [{'skill': n, 'before': round(before.preference(n, words), 3), 'after': round(after.preference(n, words), 3)}
                     for v in groups.values() for n in v]}
    if not words:
        out['note'] = ('No task words are stored for this decision, so this feedback cannot teach the hive which words '
                       'go with which skills. Pass the task text, or leave SFP_LEARN_WORDS on.')
    return out


def forget():
    """Delete everything recorded and learned. Returns what was removed."""
    removed = []
    for name in ('decisions.jsonl', 'feedback.jsonl', 'aliases.json'):
        p = _path(name)
        if os.path.exists(p):
            os.remove(p)
            removed.append(name)
    up = v1.usage_path()
    if os.path.exists(up):
        os.remove(up)
        removed.append(os.path.basename(up))
    _CACHE.clear()
    return {'removed': removed}


# -------------------------------------------------------------------- status

def status():
    """What has been recorded, what the model has learned, and whether decisions are getting better."""
    decisions = load_decisions()
    feedback = load_feedback()
    model = load_model()
    latest = {}
    for r in feedback:
        latest[(r.get('decision'), r['skill'])] = r
    counts = {v: 0 for v in VERDICTS}
    for r in latest.values():
        counts[r['verdict']] += 1
    # Of the skills the hive chose and someone judged, how many helped? Oldest half against newest half.
    judged = []
    for (did, skill), r in latest.items():
        d = decisions.get(did)
        if d and skill in d['stack'] and r['verdict'] in ('helped', 'unhelpful'):
            judged.append((r.get('t', 0), r['verdict'] == 'helped'))
    judged.sort()
    half = len(judged) // 2
    older, recent = (judged[:half], judged[half:]) if len(judged) >= 10 else ([], [])   # too few to compare halves

    def rate(xs):
        return round(sum(1 for _, ok in xs if ok) / len(xs), 3) if xs else None
    pairs = sorted((v, k) for k, v in model.w.items())
    return {
        'enabled': enabled(), 'data_folder': data_dir(), 'words_kept': keep_words(),
        'decisions': len(decisions), 'feedback': counts, 'examples': model.examples, 'associations': len(model.w),
        'chosen_skills_judged': len(judged),
        'helped_rate': {'older': rate(older), 'recent': rate(recent), 'all': rate(judged)},
        'learned_for': [{'words': k.split('|')[0], 'skill': k.split('|')[1], 'weight': round(v, 3)}
                        for v, k in reversed(pairs[-5:]) if v > 0.05],
        'learned_against': [{'words': k.split('|')[0], 'skill': k.split('|')[1], 'weight': round(v, 3)}
                            for v, k in pairs[:5] if v < -0.05],
    }


def format_status(st):
    out = []
    if not st['enabled']:
        out.append('Learning is turned off (SFP_NO_LEARNING or SFP_NO_USAGE_LOG).')
    out.append('Data folder: %s. Task words are %s.' % (st['data_folder'], 'kept as word stems' if st['words_kept'] else 'not kept'))
    fb = st['feedback']
    out.append('Decisions logged: %d. Feedback: %d helped, %d unhelpful, %d ignored, %d missing.'
               % (st['decisions'], fb['helped'], fb['unhelpful'], fb['ignored'], fb['missing']))
    out.append('Learned from %d examples: %d word-to-skill associations.' % (st['examples'], st['associations']))
    hr = st['helped_rate']
    if hr['all'] is not None:
        out.append('Chosen skills that helped: %d%% overall (%d judged)%s.' % (
            round(100 * hr['all']), st['chosen_skills_judged'],
            '; older %d%%, recent %d%%' % (round(100 * hr['older']), round(100 * hr['recent']))
            if hr['older'] is not None and hr['recent'] is not None else ''))
    else:
        out.append('No chosen skill has been judged yet. Give feedback after a task and this fills in.')
    if st['learned_for']:
        out.append('Now favours: ' + '; '.join('%s for "%s" (%+.2f)' % (x['skill'], x['words'], x['weight']) for x in st['learned_for']))
    if st['learned_against']:
        out.append('Now avoids: ' + '; '.join('%s for "%s" (%+.2f)' % (x['skill'], x['words'], x['weight']) for x in st['learned_against']))
    return '\n'.join(out)


# ---------------------------------------------------------- learning curve

def learning_curve(tests_dir=None, folds=5, seeds=5, rng_seed=7):
    """Does learning from feedback help on tasks it has not seen? Cross-validated over every task set.

    For each fold, the unlearned hive makes decisions on the training tasks, and a diligent user
    gives feedback from the answer key: skills in the key helped, skills in `avoid` were unhelpful,
    other chosen skills were ignored, and an expected skill the hive missed is reported missing.
    The model is fitted once on that feedback and scored on the held-out tasks, against the same
    hive without it. Also reports how many of the training mistakes are fixed when the same task
    is asked again, and how many held-out tasks that were right became wrong.
    """
    import random
    import tempfile
    tests_dir = tests_dir or os.path.join(os.path.dirname(HERE), 'tests')
    hist = sel.History(v1.RECIPES, [])
    with tempfile.TemporaryDirectory() as tmp:
        cases = [c for _, cs in sel.load_cases(tests_dir, tmp) for c in cs]

        def run(c, model=None):
            return sel.select(c['task'], c['project'], history=hist, model=model)

        def ok(c, res):
            return bool({x for x in c['expect'] if x in core.SKILLS} & {s['name'] for s in res['stack']})

        words = [v1.task_words(c['task'])[:WORDS_PER_DECISION] for c in cases]
        base = [run(c) for c in cases]
        base_ok = [ok(c, r) for c, r in zip(cases, base)]
        gains, retried, fixed, broke, held_base, held_new, wrong_new = [], 0, 0, 0, [], [], 0
        for seed in range(seeds):
            order = list(range(len(cases)))
            random.Random(rng_seed + seed).shuffle(order)
            for k in range(folds):
                test = set(order[k::folds])
                train = [i for i in order if i not in test]
                ex = []
                for i in train:
                    c, r = cases[i], base[i]
                    chosen = [s['name'] for s in r['stack']]
                    expect = [x for x in c['expect'] if x in core.SKILLS]
                    avoid = set(c.get('avoid', []))
                    for s in chosen:
                        verdict = 'helped' if s in expect else 'unhelpful' if s in avoid else 'ignored'
                        ex.append((features(s, words[i]), VERDICT_LABEL[verdict], VERDICT_WEIGHT[verdict]))
                    if expect and not set(expect) & set(chosen):
                        ex.append((features(expect[0], words[i]), 1, VERDICT_WEIGHT['missing']))
                model = fit(ex)
                for i in train:
                    if not base_ok[i]:
                        retried += 1
                        fixed += ok(cases[i], run(cases[i], model))
                t_ok_new = 0
                for i in test:
                    r = run(cases[i], model)
                    new = ok(cases[i], r)
                    t_ok_new += new
                    broke += base_ok[i] and not new
                    wrong_new += bool(set(cases[i].get('avoid', [])) & {s['name'] for s in r['stack']})
                held_base.append(sum(base_ok[i] for i in test) / len(test))
                held_new.append(t_ok_new / len(test))
                gains.append(held_new[-1] - held_base[-1])
    n = len(gains)
    mean = sum(gains) / n
    sd = (sum((g - mean) ** 2 for g in gains) / max(1, n - 1)) ** 0.5
    return {
        'tasks': len(cases), 'folds': folds, 'repeats': seeds,
        'heldout_without_learning': round(sum(held_base) / n, 4), 'heldout_with_learning': round(sum(held_new) / n, 4),
        'gain': round(mean, 4), 'gain_stdev_across_folds': round(sd, 4),
        'folds_improved': sum(1 for g in gains if g > 0), 'folds_worse': sum(1 for g in gains if g < 0), 'folds_total': n,
        'training_mistakes_fixed_on_retry': round(fixed / retried, 4) if retried else None,
        'heldout_tasks_that_got_worse': broke, 'wrong_technology_stacks_heldout': wrong_new,
    }


def train_from_benchmarks(tests_dir=None, reset=False):
    """Train the model from the benchmark task suites so the hive starts with a strong, tested foundation."""
    import tempfile
    tests_dir = tests_dir or os.path.join(os.path.dirname(HERE), 'tests')
    if reset:
        forget()
    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        for key, cs in sel.load_cases(tests_dir, tmp):
            if key in ('bench', 'proj'):  # train on training suites; never on heldout
                cases.extend(cs)

        trained = 0
        decisions_added = 0
        feedback_added = 0
        for c in cases:
            task = c['task']
            proj = c.get('project')
            res = decide(task, proj, learn=False)
            did = res.get('decision')
            if not did:
                continue
            decisions_added += 1
            chosen = {s['name'] for s in res.get('stack', [])}
            expect = [x for x in c.get('expect', []) if x in core.SKILLS]
            avoid = [x for x in c.get('avoid', []) if x in core.SKILLS]

            helped = [s for s in chosen if s in expect]
            unhelpful = [s for s in chosen if s in avoid]
            missing = [s for s in expect if s not in chosen]

            if helped or unhelpful or missing:
                fb_res = give_feedback(did, helped=helped, unhelpful=unhelpful, missing=missing, task=task)
                feedback_added += fb_res.get('recorded', 0)
                trained += 1

        m = load_model()
        return {
            'cases_processed': len(cases),
            'tasks_trained': trained,
            'decisions_logged': decisions_added,
            'verdicts_recorded': feedback_added,
            'model_associations': len(m.w),
            'model_examples': m.examples,
        }


if __name__ == '__main__':
    print(format_status(status()))
