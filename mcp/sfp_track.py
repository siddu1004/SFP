"""Follow what the agent is doing, estimate the phase of work, and predict what comes next.

The hive (sfp_hive.py) chooses skills from a task's words. While an agent works there is more to go on: the
files it edits, the commands it runs, the errors it hits. This module turns that activity into the phase of
work, so skills can change when the work does.

Three layers, each one simple enough to read:

1. **Evidence.** Each event (an edit, a command, an error, a prompt) gives evidence for some of the hive's
   eleven phases: editing `parser_test.go` or running `go test` is evidence of testing, a failing command of
   debugging, a Dockerfile or `git push` of shipping.
2. **Kalman filter.** One scalar filter per phase tracks how much of the current work is that phase. Between
   events the estimate relaxes towards a weak prior, and its uncertainty grows; each batch of events is a noisy
   measurement of the mix of work, and stronger evidence (a prompt, a test run) has less noise than weaker
   evidence (opening a file). The result changes smoothly instead of flipping on every event, and it carries
   its own confidence.
3. **Markov chain.** When the dominant phase changes (with hysteresis, so a single stray event does not count),
   the change is recorded. Transitions between phases are counted, starting from a prior that encodes the
   usual order of work (plan, build, test, ship, with test and debug alternating), and fade with a half-life,
   like the hive's skill history. The chain predicts the next phase, so the skills for it can be ready.

State and learned transitions live in the hive's data folder (`track_state.json`, `phases.json`).
"""
import json
import math
import os
import re
import time

import sfp_stack as v1

core = v1.core
PHASES = list(v1.PHASE_ORDER)

# Kalman filter settings. Units: phase intensity is 0..1; time is seconds.
PRIOR = 1.0 / len(PHASES)   # the level each phase relaxes to when nothing is happening
RELAX_SECONDS = 900.0       # time constant of that relaxation: after 15 quiet minutes, two thirds of the way back
Q_PER_MINUTE = 0.04         # process noise: how fast the uncertainty grows while nothing is seen (tuned, see below)
P0 = 0.05                   # starting uncertainty
R_BASE = 0.06               # measurement noise of one unit of evidence; strong evidence divides it
SWITCH_MARGIN = 0.04        # the new phase must lead the old one by this much to count as a change
SWITCH_CONFIDENCE = 0.55    # and the filter must be at least this confident
HALF_LIFE_DAYS = 30.0       # how fast learned phase transitions fade
# Q_PER_MINUTE and SWITCH_MARGIN were chosen on tests/track_sessions.json (the dev set) for accuracy with few
# extra switches; tests/track_heldout.json was written before that and is only used to check the result.

# What a file path says about the work. First match wins for each rule; a path can match several rules.
PATH_RULES = [
    (r'(^|/)(tests?|__tests__|spec|e2e|cypress|playwright)/|(_test|\.test|\.spec|_spec)\.\w+$|(^|/)test_[^/]+$|conftest\.py$', {'test': 1.0}),
    (r'(^|/)(dockerfile|docker-compose[^/]*|compose\.ya?ml|procfile|vercel\.json|netlify\.toml|fly\.toml|app\.yaml)$'
     r'|(^|/)\.github/workflows/|(^|/)(k8s|kubernetes|helm|charts|deploy|infra|terraform)/|\.tf$', {'ship': 1.0}),
    (r'(^|/)(readme|changelog|contributing)[^/]*$|(^|/)docs?/|\.mdx?$|\.rst$', {'document': 0.9}),
    (r'auth|login|session|permission|secur|crypt|secret|\.env$|csrf|oauth|jwt|policy', {'secure': 0.6}),
    (r'\.(css|scss|sass|less)$|tailwind|(^|/)(styles?|theme|design|ui|components)/|\.svg$|\.figma$|storybook', {'design': 0.6}),
    (r'bench|perf|profil|\.prof$|lighthouse|cache', {'optimize': 0.6}),
    (r'(^|/)(adr|rfcs?|plans?|specs?)/|(^|/)(plan|roadmap|design)[^/]*\.mdx?$', {'plan': 0.8}),
    (r'\.(py|js|jsx|ts|tsx|go|rs|java|kt|swift|rb|php|cs|cpp|c|h|vue|svelte|dart|scala|ex|exs)$', {'build': 0.7}),
]
PATH_RULES = [(re.compile(rx, re.I), ev) for rx, ev in PATH_RULES]

# What a command says. Checked in order; all matches add up.
COMMAND_RULES = [
    (r'\b(pytest|jest|vitest|mocha|go test|cargo test|npm (run )?test|yarn test|pnpm test|phpunit|rspec|dotnet test|'
     r'gradle(w)? test|mvn test|playwright test|cypress run|unittest|tox)\b', {'test': 1.0}),
    (r'\b(npm audit|pip-audit|bandit|semgrep|trivy|snyk|gitleaks|trufflehog|strix|codeql|safety check)\b', {'secure': 1.0}),
    (r'\b(docker (build|push|compose up)|kubectl|helm (install|upgrade)|terraform (apply|plan)|git push|'
     r'vercel|netlify deploy|fly deploy|gcloud (run|app) deploy|npm publish|twine upload|cargo publish)\b', {'ship': 1.0}),
    (r'\b(eslint|ruff|flake8|pylint|mypy|tsc --noemit|golangci-lint|clippy|prettier --check|git diff|gh pr)\b', {'review': 0.7}),
    (r'\b(npm run build|yarn build|pnpm build|tsc|go build|cargo build|make|gradle(w)? build|mvn package|vite build|next build)\b', {'build': 0.6}),
    (r'\b(npm (i|install)|pip install|uv add|cargo add|go get|yarn add|pnpm add)\b', {'build': 0.4, 'plan': 0.2}),
    (r'\b(bench|benchmark|hyperfine|lighthouse|perf |py-spy|pprof|k6|ab -n)\b', {'optimize': 1.0}),
    (r'\b(git (checkout -b|switch -c|branch))\b', {'plan': 0.5}),
    (r'\b(git commit)\b', {'review': 0.3, 'ship': 0.3}),
    (r'\b(grep|rg|find|git log|git blame|curl|wget)\b', {'research': 0.4, 'debug': 0.2}),
    (r'\b(mkdocs|sphinx|typedoc|docusaurus)\b', {'document': 1.0}),
]
COMMAND_RULES = [(re.compile(rx, re.I), ev) for rx, ev in COMMAND_RULES]

# How much to trust each kind of event: a multiplier on its evidence.
KIND_WEIGHT = {'prompt': 2.0, 'run': 1.4, 'diagnostics': 1.0, 'save': 1.0, 'edit': 0.8, 'create': 0.9,
               'delete': 0.5, 'open': 0.3, 'git': 1.0}

# The usual order of work, as prior transition counts for the Markov chain (from -> {to: count}).
PRIOR_TRANSITIONS = {
    'research': {'plan': 3, 'design': 1, 'build': 2},
    'plan': {'design': 2, 'build': 3, 'research': 1},
    'design': {'build': 3, 'plan': 1, 'review': 1},
    'build': {'test': 3, 'debug': 2, 'review': 1, 'design': 1},
    'debug': {'test': 3, 'build': 2},
    'test': {'debug': 3, 'build': 2, 'review': 2, 'secure': 1, 'ship': 1},
    'secure': {'build': 2, 'test': 1, 'review': 1, 'ship': 1},
    'review': {'build': 2, 'ship': 2, 'document': 1, 'test': 1},
    'optimize': {'test': 2, 'build': 1, 'ship': 1},
    'document': {'ship': 2, 'review': 1, 'build': 1},
    'ship': {'plan': 2, 'debug': 1, 'document': 1, 'optimize': 1},
}
PRIOR_STRENGTH = 1.0   # how much the prior weighs against what is learned (in counts)


def _empty():
    return {p: 0.0 for p in PHASES}


def evidence(event, ctx=None):
    """The evidence one event gives, per phase (0..), and the words it contributes to the task.

    `ctx` carries what earlier events established: while a failure is open (a command failed or errors were
    reported, and nothing has passed since), editing source code is debugging, not building.
    """
    ctx = ctx if ctx is not None else {}
    kind = event.get('kind', 'edit')
    ev = _empty()
    words = []
    path = (event.get('path') or '').replace('\\', '/')
    if path:
        for rx, add in PATH_RULES:
            if rx.search(path):
                for p, w in add.items():
                    ev[p] = max(ev[p], w)
        words += core.tokens(os.path.basename(path).rsplit('.', 1)[0].replace('_', ' ').replace('-', ' '))
    cmd = event.get('command') or ''
    if cmd:
        for rx, add in COMMAND_RULES:
            if rx.search(cmd):
                for p, w in add.items():
                    ev[p] += w
        words += core.tokens(cmd)[:6]
        code = event.get('exit')
        if isinstance(code, int) and code != 0:
            ev['debug'] += 0.8   # a failing command is work to fix
            ctx['failing'] = True
        elif code == 0 and any(ev[p] for p in ('test', 'build', 'secure')):
            ctx['failing'] = False   # it passes again
    if kind == 'diagnostics':
        errors = int(event.get('errors') or 0)
        if errors:
            ev['debug'] += min(1.0, 0.3 + 0.1 * errors)
            ctx['failing'] = True
    if ctx.get('failing') and kind in ('save', 'edit', 'create') and ev['build'] > 0 and not ev['test']:
        ev['debug'] += ev['build']
        ev['build'] = 0.0
    text = event.get('text') or ''
    if text:
        for p, w in v1.phase_of_text(text).items():
            ev[p] += 1.5 * w
        words = v1.task_words(text) + words
    mult = KIND_WEIGHT.get(kind, 0.8)
    return {p: w * mult for p, w in ev.items()}, words


class PhaseFilter:
    """One scalar Kalman filter per phase: x is the share of the work in that phase, P its variance."""

    def __init__(self, x=None, P=None, t=None):
        self.x = dict(x) if x else {p: PRIOR for p in PHASES}
        self.P = dict(P) if P else {p: P0 for p in PHASES}
        self.t = t

    def predict(self, now):
        """Between measurements: relax towards the prior and grow the uncertainty."""
        if self.t is None:
            self.t = now
            return
        dt = max(0.0, now - self.t)
        a = math.exp(-dt / RELAX_SECONDS)
        for p in PHASES:
            self.x[p] = a * self.x[p] + (1 - a) * PRIOR
            self.P[p] = a * a * self.P[p] + Q_PER_MINUTE * dt / 60.0
        self.t = now

    def update(self, ev):
        """Measure the mix of work from a batch of evidence. z is that mix; strong evidence is less noisy."""
        total = sum(ev.values())
        if total <= 0:
            return
        z = {p: ev[p] / total for p in PHASES}
        r = R_BASE / min(4.0, total)
        for p in PHASES:
            k = self.P[p] / (self.P[p] + r)
            self.x[p] += k * (z[p] - self.x[p])
            self.P[p] *= (1 - k)

    def shares(self):
        s = sum(max(0.0, v) for v in self.x.values()) or 1.0
        return {p: max(0.0, self.x[p]) / s for p in PHASES}

    def confidence(self, phase):
        """1 when the filter is sure of this phase's level, towards 0 as its variance grows."""
        return 1.0 / (1.0 + 20.0 * self.P[phase])

    def leader(self):
        return max(PHASES, key=lambda p: (self.x[p], -PHASES.index(p)))


class PhaseChain:
    """A first-order Markov chain over changes of phase, with a prior and fading learned counts."""

    def __init__(self, counts=None, now=None):
        self.counts = counts or {}   # {from: {to: [count, last_t]}}
        self.now = time.time() if now is None else now

    def _faded(self, c, t):
        return c * math.exp(-max(0.0, self.now - t) / 86400.0 * math.log(2) / HALF_LIFE_DAYS)

    def record(self, a, b, t=None):
        if a == b or a not in PHASES or b not in PHASES:
            return
        t = self.now if t is None else t
        row = self.counts.setdefault(a, {})
        c, last = row.get(b, [0.0, t])
        row[b] = [self._faded(c, last) + 1.0, t]

    def next(self, a):
        """P(next phase | current phase a), as a sorted list of (phase, probability)."""
        prior = PRIOR_TRANSITIONS.get(a, {})
        ptotal = sum(prior.values()) or 1.0
        learned = {b: self._faded(c, t) for b, (c, t) in self.counts.get(a, {}).items()}
        scores = {}
        for b in PHASES:
            if b == a:
                continue
            scores[b] = PRIOR_STRENGTH * prior.get(b, 0) / ptotal * 4.0 + learned.get(b, 0.0) + 0.05
        total = sum(scores.values())
        return sorted(((b, s / total) for b, s in scores.items()), key=lambda kv: -kv[1])

    def to_json(self):
        return self.counts


def _data_dir():
    import sfp_learn
    return sfp_learn.data_dir()


def _load(name, default):
    try:
        with open(os.path.join(_data_dir(), name), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(name, value):
    d = _data_dir()
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(value, f)
    os.replace(tmp, os.path.join(d, name))


def run(events, state=None, chain=None, now=None):
    """Feed events through the filter. Returns the new state and what changed; does not touch the disk."""
    state = state or {}
    f = PhaseFilter(state.get('x'), state.get('P'), state.get('t'))
    chain = chain or PhaseChain()
    current = state.get('current')
    words = list(state.get('words', []))
    ctx = dict(state.get('ctx', {}))
    changes = []
    for e in sorted(events, key=lambda e: e.get('t', 0)):
        t = float(e['t']) if e.get('t') is not None else (now if now is not None else time.time())
        f.predict(t)
        ev, w = evidence(e, ctx)
        f.update(ev)
        words = (w + words)[:24]
        lead = f.leader()
        if current is None:
            if f.x[lead] - PRIOR >= SWITCH_MARGIN:
                current = lead   # the first phase counts once some phase stands out from the prior
        elif lead != current and f.x[lead] - f.x[current] >= SWITCH_MARGIN and f.confidence(lead) >= SWITCH_CONFIDENCE:
            changes.append({'t': t, 'from': current, 'to': lead})
            chain.record(current, lead, t)
            current = lead
    if now:
        f.predict(now)
    new = {'x': f.x, 'P': f.P, 't': f.t, 'current': current, 'words': words, 'ctx': ctx}
    return new, f, chain, changes


def summary(f, chain, current, changes, words):
    shares = f.shares()
    return {
        'phase': current,
        'layer': v1.LAYER.get(current) if current else None,
        'confidence': round(f.confidence(current), 3) if current else 0.0,
        'shares': {p: round(shares[p], 3) for p in sorted(PHASES, key=lambda p: -shares[p])},
        'changed': bool(changes),
        'changes': changes[-5:],
        'next': [{'phase': p, 'probability': round(pr, 3)} for p, pr in (chain.next(current)[:3] if current else [])],
        'words': list(dict.fromkeys(words))[:12],
    }


def track(events, select=True, max_skills=4, project=None, persist=True, now=None):
    """Update the saved tracking state with new events. With `select`, also choose skills for the current
    phase and for the predicted next one, using the hive with the tracked phases as its demand."""
    state = _load('track_state.json', {}) if persist else {}
    chain = PhaseChain(_load('phases.json', {}) if persist else {})
    new, f, chain, changes = run(events, state, chain, now=now)
    out = summary(f, chain, new['current'], changes, new['words'])
    if select and new['current']:
        import sfp_hive
        task = ' '.join(out['words']) or new['current']
        hint = {p: v for p, v in out['shares'].items() if v >= 0.05}
        out['skills'] = sfp_hive.select(task, project, max_skills=max_skills, phase_hint=hint)['stack']
        if out['next']:
            nxt = out['next'][0]['phase']
            out['upcoming'] = {'phase': nxt, 'skills': [c['name'] for c in sfp_hive.select(
                task, project, max_skills=2, phase_hint={nxt: 1.0})['stack']]}
    if persist:
        _save('track_state.json', new)
        _save('phases.json', chain.to_json())
    return out


def reset():
    for name in ('track_state.json',):
        try:
            os.remove(os.path.join(_data_dir(), name))
        except OSError:
            pass


# ---------------------------------------------------------------- evaluation

def _argmax(ev):
    best = max(PHASES, key=lambda p: (ev[p], -PHASES.index(p)))
    return best if ev[best] > 0 else None


def _follow(events, method):
    """The phase each method reports after each event."""
    out, cur, recent, ctx = [], None, [], {}
    state, chain = {}, PhaseChain()
    for e in events:
        if method == 'kalman':
            state, _f, chain, _c = run([e], state, chain)
            cur = state['current']
        else:
            ev, _ = evidence(e, ctx)
            top = _argmax(ev)
            if method == 'last':
                cur = top or cur
            else:  # 'window': the most common top phase of the last three events with evidence
                if top:
                    recent = (recent + [top])[-3:]
                if recent:
                    cur = max(set(recent), key=lambda p: (recent.count(p), recent[::-1].index(p) * -1))
        out.append(cur)
    return out


def evaluate(sessions):
    """Phase accuracy and stability of the filter against two simple baselines, and next-phase prediction
    of the Markov chain with and without learning (each session predicted from the others)."""
    res = {}
    for method in ('last', 'window', 'kalman'):
        right = total = switches = true_switches = 0
        for s in sessions:
            truth = [e['truth'] for e in s['events']]
            got = _follow(s['events'], method)
            right += sum(1 for g, t in zip(got, truth) if g == t)
            total += len(truth)
            switches += sum(1 for a, b in zip(got, got[1:]) if a and b and a != b)
            true_switches += sum(1 for a, b in zip(truth, truth[1:]) if a != b)
        res[method] = {'accuracy': round(right / total, 3), 'switches': switches, 'true_switches': true_switches}
    hits_prior = hits_learned = n = 0
    for i, s in enumerate(sessions):
        chain = PhaseChain(now=0)
        for j, o in enumerate(sessions):
            if j != i:
                tr = [e['truth'] for e in o['events']]
                for a, b in zip(tr, tr[1:]):
                    chain.record(a, b, 0)
        prior = PhaseChain(now=0)
        tr = [e['truth'] for e in s['events']]
        for a, b in zip(tr, tr[1:]):
            if a != b:
                n += 1
                hits_prior += prior.next(a)[0][0] == b
                hits_learned += chain.next(a)[0][0] == b
    res['next_phase'] = {'changes': n, 'prior_only': round(hits_prior / max(1, n), 3),
                         'learned_from_other_sessions': round(hits_learned / max(1, n), 3)}
    return res
