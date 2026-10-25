#!/usr/bin/env python3
"""SFP stack engine: picks the few skills a task needs, and the order to use them in.

Skills work like photo filters. One alone does one thing; a small, well-ordered
stack gives a better result; piling on every filter makes the picture worse and
the agent slower. The engine builds that stack from four signals:

  task     the user's words, matched against every skill (the same search as sfp)
  project  the files in the project: manifests, configs and file types tell it the
           stack (Next.js, Django, Flutter ...), so a Django skill is not offered
           for a React app
  goal     the phase of work the words point to: plan, build, test, debug, review,
           secure, optimize, document, ship
  history  the skills used just before, through a Markov chain over skill
           transitions, learned from recipes and from your own recorded usage

Each candidate gets a weighted score. The stack is then chosen greedily under a
token budget, skipping skills that repeat one already chosen (maximal marginal
relevance) or that clash with it (two named visual styles), and ordered by phase:
base layers that do the work first, checks that verify it after.

Standard library only. Nothing leaves the machine. Usage is recorded only when
you call `record`, to ~/.sfp/usage.jsonl (or $SFP_USAGE_LOG), and holds skill
names, times and outcomes, never prompts or file contents.

CLI
  sfp_stack.py recommend "add tests for the checkout form" --project .
  sfp_stack.py next react-testing
  sfp_stack.py record react-testing --outcome helped
  sfp_stack.py profile .
  sfp_stack.py recipes
  sfp_stack.py evaluate      (engine against plain search, on the task sets in tests/)
"""
import heapq
import json
import math
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import sfp_mcp as core  # noqa: E402  (the catalog, tokenizer and search)


def _one(word):
    s = core.tokens(word)
    return s[0] if s else word


# ------------------------------------------------------------------ vocabulary

# Phases of work, in the order a stack applies them. Words are stemmed like the search.
PHASE_ORDER = ['research', 'plan', 'design', 'build', 'debug', 'test', 'secure', 'review', 'optimize', 'document', 'ship']
PHASE_WORDS = {
    'research': 'research investigate explore understand onboard onboarding learn compare evaluate options literature lookup unfamiliar market',
    'plan': 'plan planning architecture architect spec prd roadmap blueprint decompose scope requirement adr decision strategy',
    'design': 'ui ux layout visual style typography color colour brand aesthetic polish premium landing page interface component animation motion taste look',
    'build': 'build implement feature scaffold generate integrate setup develop endpoint app screen service server',
    'debug': 'fix bug error broken crash fail failing debug issue trace exception resolve regression stuck',
    'test': 'test tests testing tdd unit e2e coverage assert qa verify verification',
    'secure': 'security secure vulnerability vulnerabilities pentest owasp xss injection secret harden threat exploit',
    'review': 'review audit critique check lint quality standards smell refactor clean simplify',
    'optimize': 'performance optimize speed slow latency fast memory bundle cache cost token budget',
    'document': 'document documentation docs readme explain changelog tutorial guide article',
    'ship': 'deploy deployment release ship ci cd pipeline production launch publish merge rollout canary',
}
PHASE_LEX = {p: set(core.tokens(w)) for p, w in PHASE_WORDS.items()}
LAYER = {p: 'base' for p in ('research', 'plan', 'design', 'build', 'debug')}
LAYER.update({p: 'check' for p in ('test', 'secure', 'review')})
LAYER.update({p: 'finish' for p in ('optimize', 'document', 'ship')})

# How phases usually follow each other. The Markov chain backs off to this when it
# has seen too little of a skill to trust its own counts.
PHASE_NEXT = {
    'research': {'plan': .45, 'build': .25, 'design': .15, 'document': .15},
    'plan': {'build': .45, 'design': .25, 'test': .15, 'secure': .15},
    'design': {'build': .40, 'review': .30, 'test': .15, 'optimize': .15},
    'build': {'test': .40, 'review': .20, 'secure': .15, 'debug': .15, 'ship': .10},
    'debug': {'test': .50, 'review': .25, 'build': .25},
    'test': {'review': .30, 'debug': .25, 'secure': .20, 'ship': .25},
    'secure': {'review': .35, 'test': .30, 'ship': .35},
    'review': {'ship': .35, 'build': .25, 'optimize': .20, 'document': .20},
    'optimize': {'test': .40, 'review': .30, 'ship': .30},
    'document': {'ship': .60, 'review': .40},
    'ship': {'review': .40, 'document': .30, 'optimize': .30},
}

# Technologies. A skill that names technologies the project does not use is a
# mismatch; one that names the project's technologies is a fit. IMPLIES adds the
# technologies a framework always brings with it.
TECH = ('react nextjs vue nuxt angular svelte vite tailwind typescript javascript nodejs bun deno express nestjs '
        'python django fastapi flask celery pytorch golang rust java spring springboot quarkus kotlin android ios '
        'swift swiftui flutter dart php laravel ruby rails csharp dotnet fsharp cpp perl postgres postgresql mysql '
        'redis mongodb clickhouse prisma supabase docker kubernetes terraform playwright jest vitest pytest '
        'solidity evm ethereum electron expo compose harmonyos arkts jpa mybatis ktor remotion blender twitter linkedin facebook instagram reddit n8n').split()
TECH_STEMS = {_one(t) for t in TECH}
# Readable names for output: terms are compared stemmed ("postgr"), but shown whole ("postgres").
SHOW = {_one(t): t for t in TECH + ['migration', 'database', 'skill', 'plugin', 'mcp', 'llm', 'ci', 'animation']}


def show(terms):
    return [SHOW.get(t, t) for t in terms]
IMPLIES = {
    'nextjs': ['react', 'javascript', 'typescript', 'nodejs'], 'react': ['javascript'], 'vue': ['javascript'],
    'nuxt': ['vue', 'javascript', 'nodejs'], 'angular': ['typescript', 'javascript'], 'svelte': ['javascript'],
    'nestjs': ['nodejs', 'typescript'], 'express': ['nodejs', 'javascript'], 'expo': ['react', 'javascript'],
    'django': ['python'], 'fastapi': ['python'], 'flask': ['python'], 'celery': ['python'], 'pytorch': ['python'],
    'pytest': ['python'], 'flutter': ['dart'], 'springboot': ['java', 'spring'], 'quarkus': ['java'],
    'laravel': ['php'], 'rails': ['ruby'], 'swiftui': ['swift', 'ios'], 'compose': ['kotlin', 'android'],
    'ktor': ['kotlin'], 'jpa': ['java'], 'prisma': ['typescript', 'nodejs'], 'supabase': ['postgres'],
    'postgresql': ['postgres'], 'jest': ['javascript'], 'vitest': ['javascript'], 'harmonyos': ['arkts'],
}

# What files reveal. Package names map to technologies.
NPM = {'react': 'react', 'next': 'nextjs', 'vue': 'vue', 'nuxt': 'nuxt', '@angular/core': 'angular', 'svelte': 'svelte',
       'vite': 'vite', 'tailwindcss': 'tailwind', 'typescript': 'typescript', 'express': 'express',
       '@nestjs/core': 'nestjs', 'prisma': 'prisma', '@prisma/client': 'prisma', 'react-native': 'react',
       'expo': 'expo', 'electron': 'electron', 'playwright': 'playwright', '@playwright/test': 'playwright',
       'jest': 'jest', 'vitest': 'vitest', 'pg': 'postgres', 'redis': 'redis', 'ioredis': 'redis',
       'mongodb': 'mongodb', 'mongoose': 'mongodb', 'mysql2': 'mysql', '@supabase/supabase-js': 'supabase',
       'hardhat': 'solidity', 'ethers': 'evm', 'viem': 'evm', 'remotion': 'remotion',
       '@modelcontextprotocol/sdk': 'mcp', 'framer-motion': 'animation', 'motion': 'animation'}
PYPI = {'django': 'django', 'fastapi': 'fastapi', 'flask': 'flask', 'celery': 'celery', 'torch': 'pytorch',
        'pytest': 'pytest', 'mcp': 'mcp', 'psycopg': 'postgres', 'psycopg2': 'postgres', 'psycopg2-binary': 'postgres',
        'psycopg-binary': 'postgres', 'asyncpg': 'postgres',
        'redis': 'redis', 'pymongo': 'mongodb', 'sqlalchemy': 'database', 'alembic': 'migration',
        'anthropic': 'llm', 'openai': 'llm', 'langchain': 'llm', 'clickhouse-connect': 'clickhouse'}
EXT = {'.py': 'python', '.ts': 'typescript', '.tsx': 'react', '.jsx': 'react', '.js': 'javascript', '.mjs': 'javascript',
       '.vue': 'vue', '.svelte': 'svelte', '.go': 'golang', '.rs': 'rust', '.java': 'java', '.kt': 'kotlin',
       '.swift': 'swift', '.dart': 'dart', '.php': 'php', '.rb': 'ruby', '.cs': 'csharp',
       '.fs': 'fsharp', '.cpp': 'cpp', '.cc': 'cpp', '.hpp': 'cpp', '.pl': 'perl', '.sol': 'solidity',
       '.tf': 'terraform', '.ets': 'arkts', '.sql': 'database'}
SKIP_DIRS = {'node_modules', '.git', '.venv', 'venv', 'env', '__pycache__', 'dist', 'build', '.next', '.nuxt', 'target',
             'Pods', '.gradle', '.idea', '.vscode', 'coverage', '.cache', '.dart_tool', 'vendor'}
# Folders that hold other people's projects or copies of them (installed plugins, fixtures, examples): what they
# contain says nothing about the project itself.
COPIED_DIRS = {'plugins', 'third_party', 'fixtures', 'examples', 'site-packages'}

# ------------------------------------------------------------- skill profiles

SKILL_TOKENS, SKILL_TECH, SKILL_PHASE, NAME_TOKENS = {}, {}, {}, {}
WORD_JOBS = {}
for _p, _lex in PHASE_LEX.items():
    for _w in _lex:
        WORD_JOBS.setdefault(_w, []).append(_p)
for _s, _name, _desc, _cat in core.INDEX:
    SKILL_TOKENS[_s['name']] = set(_name) | set(_desc)
    NAME_TOKENS[_s['name']] = set(_name)
    # Technologies in the skill's name count. A description that lists many
    # ("works with React, Vue and Svelte") is general, not about one of them.
    _desc_tech = {w for w in _desc if w in TECH_STEMS}
    SKILL_TECH[_s['name']] = (_name & TECH_STEMS) or (_desc_tech if len(_desc_tech) <= 2 else set())
    # Each job's score is twice the words its lexicon shares with the name, plus its count in the
    # description. One pass over the skill's own words, through a word -> jobs map, finds them all.
    _count = {}
    for _w in _name:
        for _p in WORD_JOBS.get(_w, ()):
            _count[_p] = _count.get(_p, 0) + 2.0
    for _w, _c in _desc.items():
        for _p in WORD_JOBS.get(_w, ()):
            _count[_p] = _count.get(_p, 0) + _c
    SKILL_PHASE[_s['name']] = {_p: _count[_p] for _p in PHASE_ORDER if _p in _count}

# Which categories a task is about, from the words in each category's description.
CAT_TOKENS = {c: set(core.tokens(c.replace('-', ' ') + ' ' + v.get('description', '')))
              for c, v in core.CATALOG['categories'].items()}
_CAT_DF = {}
for _toks in CAT_TOKENS.values():
    for _w in _toks:
        _CAT_DF[_w] = _CAT_DF.get(_w, 0) + 1


def category_fit(words):
    """Each category's share of the task's words, weighted by how rare the word is among categories."""
    n = len(CAT_TOKENS)
    raw = {c: sum(math.log(1 + n / _CAT_DF[w]) for w in set(words) if w in toks) for c, toks in CAT_TOKENS.items()}
    top = max(raw.values()) if raw else 0
    return {c: v / top for c, v in raw.items() if v} if top else {}


_BODY = {}


def body_tokens(name):
    """About how many tokens the skill's SKILL.md costs when it is loaded."""
    if name not in _BODY:
        try:
            _BODY[name] = os.path.getsize(os.path.join(core.skill_dir(name), 'SKILL.md')) // 4
        except (OSError, ValueError):
            _BODY[name] = 1500
    return _BODY[name]


def _main_phase(name):
    v = SKILL_PHASE.get(name) or {}
    if not v:
        return 'build'
    return max(PHASE_ORDER, key=lambda p: (v.get(p, 0), -PHASE_ORDER.index(p)))


MAIN_PHASE = {n: _main_phase(n) for n in SKILL_PHASE}


def main_phase(name):
    """The job a skill does most: computed once at load, since the hive asks tens of thousands of times."""
    p = MAIN_PHASE.get(name)
    return p if p is not None else _main_phase(name)


def phase_of_text(text):
    """A distribution over phases from free text, or {} when the words carry no phase."""
    counts = {}
    for w in core.tokens(text):
        for p, lex in PHASE_LEX.items():
            if w in lex:
                counts[p] = counts.get(p, 0) + 1
    total = sum(counts.values())
    return {p: c / total for p, c in counts.items()} if total else {}


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _jaccard(x, y):
    return len(x & y) / len(x | y) if x and y else 0.0


def similarity(a, b):
    """How much two skills overlap: their names count as much as their whole descriptions."""
    return 0.5 * _jaccard(SKILL_TOKENS.get(a, set()), SKILL_TOKENS.get(b, set())) + \
        0.5 * _jaccard(NAME_TOKENS.get(a, set()), NAME_TOKENS.get(b, set()))


# ------------------------------------------------------------ project scanning

def _add(terms, signals, term, weight, why):
    for t in [term] + IMPLIES.get(term, []):
        key = _one(t)
        terms[key] = max(terms.get(key, 0.0), weight if t == term else weight * 0.6)
    signals.append('%s: %s' % (why, term))


def _read(path, limit=200000):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read(limit)
    except OSError:
        return ''


# Every file name, extension and name prefix that _scan_file below reacts to. A file matching none
# of them (most files in a project) is only counted for its language, which skips the long chain of tests.
_NAMES = frozenset(('package.json', 'pyproject.toml', 'pipfile', 'setup.py', 'setup.cfg', 'go.mod', 'cargo.toml', 'pom.xml',
                    'build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts', 'pubspec.yaml', 'gemfile',
                    'composer.json', 'package.swift', 'androidmanifest.xml', 'docker-compose.yml', 'docker-compose.yaml',
                    'compose.yaml', 'compose.yml', 'chart.yaml', 'schema.prisma', 'angular.json', 'pytest.ini', 'conftest.py',
                    'skill.md', 'plugin.json', 'app.json', '.mcp.json', 'mcp.json'))
_EXTS = frozenset(('.csproj', '.sln', '.fsproj', '.yaml', '.yml'))
_PREFIXES = ('requirements', 'dockerfile', 'hardhat.config', 'foundry.toml', 'next.config', 'nuxt.config', 'vite.config',
             'tailwind.config', 'playwright.config', 'jest.config', 'vitest.config')


def _scan_file(f, d, depth, base, terms, signals):
    low = f.lower()
    ext = os.path.splitext(low)[1]
    if low not in _NAMES and ext not in _EXTS and not low.startswith(_PREFIXES):
        return EXT.get(ext)
    full = os.path.join(d, f)
    if low == 'package.json' and depth <= 2:
        try:
            pkg = json.loads(_read(full))
        except ValueError:
            pkg = {}
        deps = {}
        for k in ('dependencies', 'devDependencies', 'peerDependencies'):
            if isinstance(pkg.get(k), dict):
                deps.update(pkg[k])
        _add(terms, signals, 'nodejs', 1.5, 'package.json')
        for dep in deps:
            if dep in NPM:
                _add(terms, signals, NPM[dep], 3.0, 'package.json')
    elif low in ('requirements.txt', 'pyproject.toml', 'pipfile', 'setup.py', 'setup.cfg') or (
            low.startswith('requirements') and low.endswith('.txt')):
        text = _read(full).lower()
        _add(terms, signals, 'python', 1.5, f)
        for pkg, tech in PYPI.items():
            if re.search(r'(^|[\s"\'\[,])%s([\s"\'<>=~!\[\],;]|$)' % re.escape(pkg), text, re.M):
                _add(terms, signals, tech, 3.0, f)
    elif low == 'go.mod':
        _add(terms, signals, 'golang', 3.0, f)
    elif low == 'cargo.toml':
        _add(terms, signals, 'rust', 3.0, f)
    elif low in ('pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts'):
        text = _read(full).lower()
        _add(terms, signals, 'kotlin' if low.endswith('.kts') else 'java', 2.5, f)
        for needle, tech in (('spring-boot', 'springboot'), ('quarkus', 'quarkus'), ('com.android', 'android'),
                             ('compose', 'compose'), ('ktor', 'ktor'), ('kotlin', 'kotlin'), ('mybatis', 'mybatis'),
                             ('jakarta.persistence', 'jpa'), ('data-jpa', 'jpa')):
            if needle in text:
                _add(terms, signals, tech, 3.0, f)
    elif low == 'pubspec.yaml':
        _add(terms, signals, 'flutter' if 'flutter' in _read(full) else 'dart', 3.0, f)
    elif low == 'gemfile':
        _add(terms, signals, 'rails' if 'rails' in _read(full) else 'ruby', 3.0, f)
    elif low == 'composer.json':
        _add(terms, signals, 'laravel' if 'laravel' in _read(full) else 'php', 3.0, f)
    elif ext in ('.csproj', '.sln'):
        _add(terms, signals, 'dotnet', 3.0, f)
        _add(terms, signals, 'csharp', 2.0, f)
    elif ext == '.fsproj':
        _add(terms, signals, 'fsharp', 3.0, f)
    elif low == 'package.swift':
        _add(terms, signals, 'swift', 3.0, f)
    elif low == 'androidmanifest.xml':
        _add(terms, signals, 'android', 3.0, f)
    elif low.startswith('dockerfile') or low in ('docker-compose.yml', 'docker-compose.yaml', 'compose.yaml', 'compose.yml'):
        _add(terms, signals, 'docker', 2.5, f)
    elif low == 'chart.yaml' or (ext in ('.yaml', '.yml') and base in ('k8s', 'kubernetes', 'helm')):
        _add(terms, signals, 'kubernetes', 2.5, f)
    elif low == 'schema.prisma':
        _add(terms, signals, 'prisma', 3.0, f)
    elif low.startswith(('hardhat.config', 'foundry.toml')):
        _add(terms, signals, 'solidity', 3.0, f)
    elif low.startswith('next.config'):
        _add(terms, signals, 'nextjs', 3.0, f)
    elif low.startswith('nuxt.config'):
        _add(terms, signals, 'nuxt', 3.0, f)
    elif low == 'angular.json':
        _add(terms, signals, 'angular', 3.0, f)
    elif low.startswith('vite.config'):
        _add(terms, signals, 'vite', 2.5, f)
    elif low.startswith('tailwind.config'):
        _add(terms, signals, 'tailwind', 2.5, f)
    elif low.startswith('playwright.config'):
        _add(terms, signals, 'playwright', 3.0, f)
    elif low.startswith('jest.config'):
        _add(terms, signals, 'jest', 2.5, f)
    elif low.startswith('vitest.config'):
        _add(terms, signals, 'vitest', 2.5, f)
    elif low in ('pytest.ini', 'conftest.py'):
        _add(terms, signals, 'pytest', 2.5, f)
    elif low == 'skill.md':
        _add(terms, signals, 'skill', 2.0, f)
    elif low == 'plugin.json' and base == '.claude-plugin':
        _add(terms, signals, 'plugin', 2.5, '.claude-plugin/plugin.json')
    elif low == 'app.json' and '"expo"' in _read(full, 4000):
        _add(terms, signals, 'expo', 3.0, f)
    elif low in ('.mcp.json', 'mcp.json'):
        _add(terms, signals, 'mcp', 2.0, f)
    return EXT.get(ext)


def scan_project(path, max_files=5000, max_depth=5):
    """Fingerprint a project from its files. Returns technology weights and the evidence for them."""
    terms, signals = {}, []
    if not path or not os.path.isdir(path):
        return {'terms': terms, 'signals': signals, 'files': 0}
    root = os.path.abspath(path)
    ext_count, seen = {}, 0
    for d, dirs, files in os.walk(root):
        rel_os = '.' if d == root else os.path.relpath(d, root)
        depth = 0 if d == root else rel_os.count(os.sep) + 1
        dirs[:] = sorted(x for x in dirs if x in ('.github', '.claude-plugin')
                         or (x not in SKIP_DIRS and x not in COPIED_DIRS and not x.startswith('.')))
        if depth >= max_depth:
            dirs[:] = []
        base = os.path.basename(d)
        rel = rel_os.replace(os.sep, '/')
        if rel.endswith('.github/workflows'):
            _add(terms, signals, 'ci', 2.0, '.github/workflows')
        if base == 'migrations':
            _add(terms, signals, 'migration', 2.0, rel + '/')
        if base.endswith('.xcodeproj'):
            _add(terms, signals, 'ios', 3.0, base)
        if base == 'supabase' and depth == 1:
            _add(terms, signals, 'supabase', 3.0, 'supabase/')
        for f in sorted(files):
            seen += 1
            if seen > max_files:
                break
            lang = _scan_file(f, d, depth, base, terms, signals)
            if lang:
                ext_count[lang] = ext_count.get(lang, 0) + 1
        if seen > max_files:
            break
    code = sum(ext_count.values())
    for lang, n in sorted(ext_count.items(), key=lambda kv: -kv[1]):
        share = n / code if code else 0
        if share >= 0.05 or n >= 20:
            _add(terms, signals, lang, 1.0 + 1.0 * share, '%d %s files' % (n, lang))  # a language says less than a framework
    return {'terms': terms, 'signals': list(dict.fromkeys(signals))[:40], 'files': min(seen, max_files)}


# --------------------------------------------------------------- Markov model

RECIPES_PATH = os.path.join(HERE, 'stack_recipes.json')
SEED_WEIGHT = 2.0


def load_recipes():
    try:
        with open(RECIPES_PATH, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return [r for r in data.get('recipes', []) if all(n in core.SKILLS for n in r.get('skills', []))]


RECIPES = load_recipes()


def usage_path():
    return os.environ.get('SFP_USAGE_LOG') or os.path.join(os.path.expanduser('~'), '.sfp', 'usage.jsonl')


def read_usage():
    path = usage_path()
    events = []
    if not os.path.isfile(path):
        return events
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e, dict) and e.get('skill') in core.SKILLS:
                events.append(e)
    return events


def sessions(events, gap=2 * 3600):
    """Group events into sessions by id, or by a two-hour gap when there is no id."""
    out, by_id, current, last_t = [], {}, [], None
    for e in sorted(events, key=lambda e: e.get('t', 0)):
        if e.get('session'):
            by_id.setdefault(e['session'], []).append(e['skill'])
            continue
        t = e.get('t', 0)
        if last_t is not None and t - last_t > gap and current:
            out.append(current)
            current = []
        current.append(e['skill'])
        last_t = t
    if current:
        out.append(current)
    return out + list(by_id.values())


class Markov:
    """First-order chain over skills, smoothed by backing off to categories and phases.

    P(b | a) = lam_a * c(a, b) / c(a) + (1 - lam_a) * Pback(b | a)
    lam_a    = c(a) / (c(a) + distinct followers of a)            (Witten-Bell)
    Pback    = 0.5 * P(cat b | cat a) / |cat b| + 0.5 * P(phase b | phase a) / |phase b|

    A skill seen often follows its own history; a rare one borrows from what
    usually follows its category and its phase of work.
    """

    def __init__(self, recipes=(), events=()):
        self.c, self.total, self.cat_c, self.cat_total, self.outcome = {}, {}, {}, {}, {}
        self._z = {}
        self._bo = {}
        events = list(events)
        seqs = [(r['skills'], SEED_WEIGHT) for r in recipes] + [(s, 1.0) for s in sessions(events)]
        for seq, w in seqs:
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
        self.cat_size, self.phase_size = {}, {}
        for n, s in core.SKILLS.items():
            self.cat_size[s['category']] = self.cat_size.get(s['category'], 0) + 1
            p = main_phase(n)
            self.phase_size[p] = self.phase_size.get(p, 0) + 1

    def back_off(self, a, b):
        """What usually follows a skill like a: a depends on a's category and job, b on b's.

        So the value is computed once per (category, job, category, job) and reused; the 559
        skills fall into a few hundred such groups, and a prediction asks about all of them.
        """
        ca, cb = core.SKILLS[a]['category'], core.SKILLS[b]['category']
        pa, pb = main_phase(a), main_phase(b)
        key = (ca, pa, cb, pb)
        v = self._bo.get(key)
        if v is None:
            # Unseen category pairs get a prior in proportion to category size, so a
            # one-skill category is not predicted as often as a sixty-skill one.
            prior = 0.5 * (ca == cb) + 0.5 * self.cat_size[cb] / len(core.SKILLS)
            if self.cat_total.get(ca):
                p_cat = (self.cat_c[ca].get(cb, 0) + prior) / (self.cat_total[ca] + 1.0)
            else:
                p_cat = prior
            p_phase = PHASE_NEXT.get(pa, {}).get(pb, 0.02)
            v = self._bo[key] = 0.5 * p_cat / self.cat_size[cb] + 0.5 * p_phase / self.phase_size.get(pb, 1)
        return v

    def _groups(self):
        if not hasattr(self, '_grp'):
            self._grp, self._key = {}, {}
            for b in core.SKILLS:
                k = (core.SKILLS[b]['category'], main_phase(b))
                self._grp.setdefault(k, []).append(b)
                self._key[b] = k
        return self._grp

    def _norm(self, a):
        """The back-off's total over every possible next skill, so each row sums to 1."""
        if a not in self._z:
            self._z[a] = sum(self.back_off(a, b) for b in core.SKILLS if b != a) or 1.0
        return self._z[a]

    def prob(self, a, b):
        if a not in core.SKILLS or b not in core.SKILLS or a == b:
            return 0.0
        n = self.total.get(a, 0)
        back = self.back_off(a, b) / self._norm(a)
        if not n:
            return back
        lam = n / (n + len(self.c[a]))
        return lam * self.c[a].get(b, 0) / n + (1 - lam) * back

    def next(self, a, limit=5, exclude=()):
        if a not in core.SKILLS:
            return []
        n = self.total.get(a, 0)
        z = self._norm(a)
        row = self.c.get(a) or {}
        lam = n / (n + len(row)) if n else 0.0
        # Skills in the same category and job share a back-off, so score each group once.
        group_score = {}
        for key, members in self._groups().items():
            back = self.back_off(a, members[0]) / z
            group_score[key] = (1 - lam) * back if n else back
        scores = []
        for b in core.SKILLS:
            if b == a or b in exclude or b == 'sfp' or b == 'sfp-hive':
                continue
            seen = row.get(b, 0)
            s = group_score[self._key[b]]
            if seen:
                s = lam * seen / n + s
            scores.append((s, b))
        return heapq.nsmallest(limit, scores, key=lambda x: (-x[0], x[1]))

    def prior(self, name):
        """Posterior mean of 'this skill helped', centred on 0: Beta(1 + helped, 1 + unhelpful)."""
        h, u = self.outcome.get(name, (0, 0))
        return (1.0 + h) / (2.0 + h + u) - 0.5


def model():
    return Markov(RECIPES, read_usage())


def record(skill, outcome=None, session=None):
    """Append one usage event to the local log. Only skill names, times and outcomes are kept."""
    name = core.resolve_name(skill)
    if not name:
        raise ValueError('no skill named %r' % skill)
    if outcome not in (None, 'helped', 'unhelpful'):
        raise ValueError('outcome must be helped or unhelpful')
    if os.environ.get('SFP_NO_USAGE_LOG'):
        return {'recorded': False, 'reason': 'SFP_NO_USAGE_LOG is set'}
    event = {'t': int(time.time()), 'skill': name}
    if outcome:
        event['outcome'] = outcome
    if session:
        event['session'] = str(session)[:80]
    path = usage_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(event) + '\n')
    return {'recorded': True, 'path': path, 'event': event}


# ------------------------------------------------------------------- scoring

# How much each signal moves a skill's score. The task's words decide what is
# relevant; every other signal multiplies that relevance up or down, so a skill
# that matches the project but not the task can never outrank one that matches the task.
WEIGHTS = {'category': 0.3, 'phase': 0.30, 'project': 0.50, 'history': 0.30, 'outcome': 0.40, 'mismatch': 0.60, 'unasked': 0.20}
REDUNDANCY = 0.5
GENERAL_FIT = 0.6

# Verbs that say a task exists but not what it is about. They are dropped before
# matching, so "add tests" is about tests, not about every skill that mentions adding.
WEAK = frozenset(core.tokens('add adding write writing create creating new use using get getting help work working '
                             'thing stuff some something'))

# Names people write in two words, or that only read as a technology when capitalised.
PHRASES = ((re.compile(r'spring[\s-]+boot', re.I), 'springboot'), (re.compile(r'\bGo\b'), 'golang'),
           (re.compile(r'next[\s.]?js', re.I), 'nextjs'), (re.compile(r'\bk8s\b', re.I), 'kubernetes'),
           (re.compile(r'\bpostgresql\b', re.I), 'postgres'))


# Words people use for the same thing that the stemmer does not join.
SYNONYMS = {_one(a): _one(b) for a, b in (
    ('accessible', 'accessibility'), ('a11y', 'accessibility'), ('perf', 'performance'),
    ('faster', 'performance'), ('slow', 'performance'), ('auth', 'authentication'), ('login', 'authentication'),
    ('pentest', 'penetration'), ('vuln', 'vulnerability'), ('vulns', 'vulnerability'), ('db', 'database'),
    ('k8', 'kubernetes'), ('pr', 'pull'), ('docs', 'documentation'), ('ci', 'pipeline'))}


def task_words(text):
    for pattern, word in PHRASES:
        text = pattern.sub(' %s ' % word, text)
    words = [SYNONYMS.get(w, w) for w in core.tokens(text)]
    strong = [w for w in words if w not in WEAK]
    return strong or words


def recommend(task, project=None, goal=None, after=(), budget=12000, max_skills=4, chain=None, scan=None):
    """Build a skill stack for a task. Returns the stack, the evidence, and likely next skills."""
    t0 = time.time()
    text = ' '.join(x for x in (task or '', goal or '') if x)
    after = [n for n in (core.resolve_name(a) for a in (after or [])) if n]
    chain = chain or model()
    if scan is None:
        scan = scan_project(project) if project else {'terms': {}, 'signals': [], 'files': 0}

    # Context technologies: what the project uses, plus anything the task names outright.
    ctx = dict(scan['terms'])
    words = task_words(text)
    query = ' '.join(words)
    said = {}  # stem -> the word the user wrote, for readable reasons
    for raw in core.raw_words(text):
        for s in core.tokens(raw):
            said.setdefault(SYNONYMS.get(s, s), raw)
    for w in words:
        if w in TECH_STEMS:
            ctx[w] = max(ctx.get(w, 0), 4.0)
            for imp in IMPLIES.get(w, []):
                ctx[_one(imp)] = max(ctx.get(_one(imp), 0), 2.4)
    ctx_tech = {t for t in ctx if t in TECH_STEMS}
    top_ctx = max(ctx.values()) if ctx else 1.0

    # The goal, when given, says more about the phase of work than the task does.
    want_phase = dict(phase_of_text(goal or '') or phase_of_text(task or ''))
    if goal and task:
        for p, v in phase_of_text(task).items():
            want_phase[p] = want_phase.get(p, 0) * 0.7 + v * 0.3

    # Candidates: what the words match, what the words plus the project's main
    # technologies match, and what usually follows the skills just used.
    rel = {}
    if words:
        for score, s in core.scored_search(query, limit=150):
            rel[s['name']] = max(rel.get(s['name'], 0), score)
        if ctx_tech:
            lead = sorted(ctx_tech, key=lambda t: (-ctx[t], t))[:3]
            for score, s in core.scored_search(query + ' ' + ' '.join(lead), limit=80):
                rel[s['name']] = max(rel.get(s['name'], 0), 0.8 * score)
    hist = {b: p for p, b in chain.next(after[-1], limit=15, exclude=after)} if after else {}
    top_rel = max(rel.values()) if rel else 1.0
    cat_fit = category_fit(words)
    top_hist = max(hist.values()) if hist else 1.0

    scored = []
    for name in set(rel) | set(hist):
        if name in after or name in ('sfp', 'sfp-hive'):
            continue
        r = rel.get(name, 0) / top_rel
        tech = SKILL_TECH.get(name, set())
        fit_terms = sorted(tech & set(ctx))
        fit = max((ctx[t] for t in fit_terms), default=0) / top_ctx
        mismatch = 1.0 if tech and ctx_tech and not (tech & ctx_tech) else 0.0
        # With no project to go on, a general skill beats one for a technology nobody named.
        unasked = 1.0 if tech and not ctx_tech else 0.0
        ph = cosine(want_phase, SKILL_PHASE.get(name, {}))
        h = hist.get(name, 0) / top_hist if hist else 0.0
        o = chain.prior(name)
        factor = 1 + WEIGHTS['category'] * cat_fit.get(core.SKILLS[name]['category'], 0)
        if want_phase and SKILL_PHASE.get(name):
            factor *= 1 - WEIGHTS['phase'] / 2 + WEIGHTS['phase'] * ph
        # A general skill (no technology of its own) suits any project fairly well; a
        # skill for one technology beats it only when that technology is clearly in use.
        factor *= 1 + WEIGHTS['project'] * (fit if tech else GENERAL_FIT)
        factor *= 1 - WEIGHTS['mismatch'] * mismatch
        factor *= 1 - WEIGHTS['unasked'] * unasked
        factor *= 1 + WEIGHTS['history'] * h
        factor *= 1 + WEIGHTS['outcome'] * o
        score = r * factor
        hit = sorted(set(words) & SKILL_TOKENS.get(name, set()))
        reasons = []
        if r:
            reasons.append('task words: ' + ', '.join(said.get(w, w) for w in hit[:4]) if hit else 'matches the task')
        if fit_terms:
            reasons.append('fits project: ' + ', '.join(show(fit_terms[:3])))
        if mismatch:
            reasons.append('for %s, not this project' % ', '.join(show(sorted(tech)[:2])))
        if h:
            reasons.append('often follows ' + after[-1])
        if o > 0.1:
            reasons.append('helped before')
        scored.append({'name': name, 'score': score, 'relevance': r, 'task_hits': len(hit), 'fit': fit, 'phase_fit': ph, 'history': h,
                       'mismatch': mismatch, 'reasons': reasons})
    scored.sort(key=lambda x: (-x['score'], x['name']))

    # Greedy stack: best marginal score under the budget, no near-duplicates, one named look.
    stack, used, spent = [], set(), 0
    # A stack member must match the task's own words (matching only the project is
    # not enough) and must not be for another technology. The cut-off is set by the
    # best eligible skill, so an excluded one cannot push everything else out.
    eligible = [c for c in scored if c['task_hits'] and not c['mismatch']]
    floor = 0.45 * eligible[0]['score'] if eligible else 0
    pool = [c for c in eligible if c['score'] >= floor]
    styles_named = sum(1 for w in core.raw_words(text) if core.SKILLS.get(w, {}).get('category') == 'design-styles')
    while pool and len(stack) < max_skills:
        best, best_val = None, None
        for c in pool:
            red = max((similarity(c['name'], s['name']) for s in stack), default=0.0)
            val = c['score'] - REDUNDANCY * red
            if best_val is None or val > best_val:
                best, best_val = c, val
        pool.remove(best)
        if stack and best_val < floor * 0.8:
            break
        if core.SKILLS[best['name']]['category'] == 'design-styles' and styles_named < 2 and any(
                core.SKILLS[s['name']]['category'] == 'design-styles' for s in stack):
            continue
        # One filter per role: a second skill for the same category and phase of work
        # repeats the first instead of adding to it.
        slot = (core.SKILLS[best['name']]['category'], main_phase(best['name']))
        if any((s['category'], s['phase']) == slot for s in stack):
            continue
        cost = body_tokens(best['name'])
        if stack and spent + cost > budget:
            continue
        best['tokens'] = cost
        best['phase'] = slot[1]
        best['category'] = slot[0]
        stack.append(best)
        used.add(best['name'])
        spent += cost
    stack.sort(key=lambda c: (PHASE_ORDER.index(c['phase']), -c['score']))
    for c in stack:
        c['layer'] = LAYER[c['phase']]
        c['category'] = core.SKILLS[c['name']]['category']
        c['path'] = core.SKILLS[c['name']]['path'] + '/SKILL.md'

    # A recipe matches when it shares most of the stack, or its goal reads like the task.
    recipe, best_val = None, 0.0
    for rc in RECIPES:
        overlap = len(used & set(rc['skills'])) / max(1, min(len(used), len(rc['skills'])))
        goal_words = set(core.tokens(rc['goal']))
        goal_sim = len(set(words) & goal_words) / max(1, len(goal_words))
        val = max(overlap, goal_sim)
        if val > best_val and (overlap >= 0.5 or goal_sim >= 0.5):
            recipe, best_val = rc, val

    nxt = []
    if stack:
        nxt = [{'name': b, 'probability': round(p, 4)}
               for p, b in chain.next(stack[-1]['name'], limit=40, exclude=used | set(after))
               if not (SKILL_TECH.get(b) and ctx_tech and not (SKILL_TECH[b] & ctx_tech))][:3]

    return {
        'task': task, 'goal': goal,
        'project': {'technologies': show(sorted(ctx_tech, key=lambda t: (-ctx[t], t))[:8]), 'evidence': scan['signals'][:8],
                    'files_scanned': scan['files']},
        'phases': {p: round(v, 2) for p, v in sorted(want_phase.items(), key=lambda kv: -kv[1])},
        'stack': [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in c.items()} for c in stack],
        'tokens': spent,
        'recipe': recipe and {'name': recipe['name'], 'skills': recipe['skills']},
        'next': nxt,
        'considered': len(scored),
        'ms': int((time.time() - t0) * 1000),
    }


# ---------------------------------------------------------------- evaluation

def evaluate(tests_dir=None):
    """Score the engine against plain search on the task sets in tests/. Used by the tests and the README.

    Without a project: the 91 search tasks; a stack counts as right if it holds
    any expected skill, and search gets the same number of results as the stack.
    With a project: tests/stack_eval.json builds small fake projects and also
    counts stacks that hold a skill for the wrong technology.
    """
    import tempfile
    tests_dir = tests_dir or os.path.join(os.path.dirname(HERE), 'tests')
    chain = Markov(RECIPES, [])  # recipes only, so personal usage never changes the published figures
    out = {}
    cases = []
    for name in ('search_eval.json', 'search_holdout.json', 'search_fresh.json'):
        path = os.path.join(tests_dir, name)
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                cases += json.load(f)
    hit = s_hit = first = size = tokens = ms = 0
    for c in cases:
        want = {x for x in c['expect'] if x in core.SKILLS}
        res = recommend(c['task'], chain=chain)
        names = [x['name'] for x in res['stack']]
        top = [s['name'] for s in core.search(c['task'], limit=max(1, len(names)))]
        hit += bool(want & set(names))
        s_hit += bool(want & set(top))
        first += bool(names and max(res['stack'], key=lambda x: x['score'])['name'] in want)
        size += len(names)
        tokens += res['tokens']
        ms += res['ms']
    n = len(cases)
    out.update(bench_n=n, bench_hit=hit / n if n else 0, bench_search_hit=s_hit / n if n else 0,
               bench_first=first / n if n else 0, avg_size=size / n if n else 0,
               avg_tokens=tokens / n if n else 0, avg_ms=ms / n if n else 0)

    path = os.path.join(tests_dir, 'stack_eval.json')
    if os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        p_hit = p_s_hit = wrong = s_wrong = 0
        with tempfile.TemporaryDirectory() as tmp:
            for proj, files in data['projects'].items():
                for rel, body in files.items():
                    f = os.path.join(tmp, proj, rel)
                    os.makedirs(os.path.dirname(f), exist_ok=True)
                    with open(f, 'w', encoding='utf-8') as fh:
                        fh.write(body)
            for c in data['cases']:
                res = recommend(c['task'], os.path.join(tmp, c['project']), chain=chain)
                names = {x['name'] for x in res['stack']}
                top = {s['name'] for s in core.search(c['task'], limit=max(1, len(names)))}
                p_hit += bool(set(c['expect']) & names)
                p_s_hit += bool(set(c['expect']) & top)
                wrong += bool(set(c['avoid']) & names)
                s_wrong += bool(set(c['avoid']) & top)
        m = len(data['cases'])
        out.update(proj_n=m, proj_hit=p_hit / m, proj_search_hit=p_s_hit / m, proj_wrong=wrong, proj_search_wrong=s_wrong)
    return out


# ----------------------------------------------------------------------- CLI

def format_stack(res):
    out = ['Stack for: %s' % res['task'],
           'Project: %s' % (', '.join(res['project']['technologies']) or 'no technologies detected')]
    if res['phases']:
        out.append('Phase of work: %s' % ', '.join('%s %d%%' % (p, v * 100) for p, v in res['phases'].items()))
    out.append('')
    if not res['stack']:
        out.append('No skill fits well. Carry on without one, or describe the task in more detail.')
    for i, c in enumerate(res['stack'], 1):
        out.append('%d. [%s] %s  (%s, %s, about %s tokens)' % (i, c['layer'], c['name'], c['category'], c['phase'],
                                                               format(c['tokens'], ',')))
        out.append('   why: %s' % ('; '.join(c['reasons']) or 'relevant'))
        out.append('   read: %s' % c['path'])
    out.append('')
    out.append('Instructions to load: about %s tokens.' % format(res['tokens'], ','))
    if res['recipe']:
        out.append('Matching recipe: %s (%s)' % (res['recipe']['name'], ' -> '.join(res['recipe']['skills'])))
    if res['next']:
        out.append('Likely next: %s' % ', '.join(n['name'] for n in res['next']))
    out.append('Chose from %d candidates in %d ms.' % (res['considered'], res['ms']))
    return '\n'.join(out)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Pick and order the SFP skills a task needs.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('recommend', help='build a skill stack for a task')
    r.add_argument('task')
    r.add_argument('--project', help='project folder to fingerprint')
    r.add_argument('--goal', help='what the user wants to achieve, if different from the task')
    r.add_argument('--after', default='', help='comma-separated skills already used, most recent last')
    r.add_argument('--budget', type=int, default=12000, help='token budget for loaded instructions (default 12000)')
    r.add_argument('--max', type=int, default=4, help='most skills in the stack (default 4)')
    r.add_argument('--json', action='store_true')
    n = sub.add_parser('next', help='predict the skills likely to follow one')
    n.add_argument('skill')
    n.add_argument('--limit', type=int, default=5)
    n.add_argument('--json', action='store_true')
    rec = sub.add_parser('record', help='record that a skill was used (local file only)')
    rec.add_argument('skill')
    rec.add_argument('--outcome', choices=['helped', 'unhelpful'])
    rec.add_argument('--session')
    p = sub.add_parser('profile', help='show what the engine detects in a project')
    p.add_argument('path', nargs='?', default='.')
    sub.add_parser('recipes', help='list the named stacks')
    sub.add_parser('evaluate', help='score the engine against plain search on the task sets in tests/')
    a = ap.parse_args(argv)

    if a.cmd == 'recommend':
        res = recommend(a.task, a.project, a.goal, [x for x in a.after.split(',') if x.strip()], a.budget, a.max)
        print(json.dumps(res, indent=1) if a.json else format_stack(res))
    elif a.cmd == 'next':
        name = core.resolve_name(a.skill)
        if not name:
            raise SystemExit('no skill named %r' % a.skill)
        res = [{'name': b, 'probability': round(pr, 4)} for pr, b in model().next(name, a.limit)]
        print(json.dumps(res, indent=1) if a.json else '\n'.join('%-40s %.3f' % (x['name'], x['probability']) for x in res))
    elif a.cmd == 'record':
        print(json.dumps(record(a.skill, a.outcome, a.session)))
    elif a.cmd == 'profile':
        s = scan_project(a.path)
        ranked = sorted(s['terms'].items(), key=lambda kv: -kv[1])
        print('Files scanned: %d' % s['files'])
        print('Technologies: ' + (', '.join('%s %.1f' % kv for kv in ranked[:12]) or 'none'))
        print('Evidence:\n  ' + '\n  '.join(s['signals'][:20]))
    elif a.cmd == 'evaluate':
        print(json.dumps({k: round(v, 3) if isinstance(v, float) else v for k, v in evaluate().items()}, indent=1))
    elif a.cmd == 'recipes':
        for rc in RECIPES:
            print('%-24s %s\n%24s %s' % (rc['name'], rc['goal'], '', ' -> '.join(rc['skills'])))


if __name__ == '__main__':
    main()
