#!/usr/bin/env python3
"""Who is working here: the engineer's role, read from the project, and how well the library covers their stack.

A backend engineer on a Django and Postgres service, a firmware engineer on Arduino and KiCad files, a data scientist on
notebooks: each wants different skills before a word of the task is read. The role comes from the files (how many of
each kind, and the frameworks the project fingerprint found) and gives the skills of the role's categories a small push
in the hive (sfp_hive.base_quality).

It also says where the library is thin for this person: a stack the project uses that few or no skills cover (Elixir,
Verilog, Simulink...). That is a gap the hive can fill by research (sfp_research.py).

CLI
  sfp_role.py .                        the role of the project in this folder, and its coverage gaps
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sfp_mcp as core  # noqa: E402
import sfp_stack as v1  # noqa: E402

# role: (file kinds that point to it, technologies that point to it, the library categories that serve it)
ROLES = {
    'backend': ({'.py', '.go', '.java', '.rb', '.php', '.cs', '.ex', '.exs', '.scala', '.sql', '.proto', '.graphql'},
                'django fastapi flask express nestjs springboot spring quarkus laravel rails ktor postgres mysql redis '
                'mongodb prisma celery jpa mybatis clickhouse supabase',
                ('backend', 'languages', 'devops', 'security', 'testing-quality')),
    'frontend': ({'.tsx', '.jsx', '.vue', '.svelte', '.css', '.scss', '.html', '.astro'},
                 'react nextjs vue nuxt angular svelte vite tailwind animation', ('frontend', 'design-styles', 'testing-quality')),
    'mobile': ({'.swift', '.kt', '.dart', '.mm', '.xib', '.storyboard'},   # not .m: MATLAB uses it as much as Objective-C
               'android ios swiftui flutter expo compose harmonyos arkts', ('mobile', 'languages', 'testing-quality')),
    'data-ml': ({'.ipynb', '.parquet', '.csv', '.onnx', '.safetensors'}, 'pytorch llm', ('ai-ml', 'research-docs')),
    'devops': ({'.tf', '.hcl', '.yaml', '.yml', '.sh', '.ps1'}, 'docker kubernetes terraform', ('devops', 'security')),
    'embedded-hardware': ({'.c', '.h', '.ino', '.v', '.sv', '.vhd', '.vhdl', '.slx', '.mdl', '.kicad_sch', '.kicad_pcb',
                           '.kicad_pro', '.asc', '.cir', '.ld', '.s', '.hex'}, '', ('science-hardware', 'engineering')),
    'web3': ({'.sol', '.move', '.cairo'}, 'solidity evm ethereum', ('web3', 'security')),
    'agent-builder': ({'.prompt'}, 'mcp llm', ('agents', 'agent-dev', 'ai-gateway')),
}
# File kinds that name a stack the vocabulary of the hive does not know, so its coverage can still be counted.
STACK_NAMES = {'.ex': 'elixir', '.exs': 'elixir', '.scala': 'scala', '.c': 'c', '.h': 'c', '.ino': 'arduino',
               '.v': 'verilog', '.sv': 'systemverilog', '.vhd': 'vhdl', '.vhdl': 'vhdl', '.slx': 'simulink',
               '.mdl': 'simulink', '.kicad_sch': 'kicad', '.kicad_pcb': 'kicad', '.asc': 'ltspice', '.cir': 'spice',
               '.move': 'move', '.cairo': 'cairo', '.zig': 'zig', '.nim': 'nim', '.jl': 'julia', '.r': 'r', '.lua': 'lua',
               '.hs': 'haskell', '.ml': 'ocaml', '.clj': 'clojure', '.erl': 'erlang', '.gd': 'godot', '.unity': 'unity'}
TECH_ROLE = {}
for _role, (_exts, _tech, _cats) in ROLES.items():
    for _t in _tech.split():
        TECH_ROLE.setdefault(v1._one(_t), _role)
THIN = 3          # a stack with fewer skills than this is a gap
MAX_FILES = 4000


def count_files(path, max_files=MAX_FILES, max_depth=5):
    """{extension: count} of the project's own files (dependencies, builds and copies are skipped)."""
    counts, seen = {}, 0
    base = os.path.abspath(path)
    for d, dirs, files in os.walk(base):
        depth = os.path.relpath(d, base).count(os.sep)
        dirs[:] = [x for x in dirs if x not in v1.SKIP_DIRS and x not in v1.COPIED_DIRS and not x.startswith('.')
                   and depth < max_depth]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if f.lower() == 'dockerfile':
                ext = '.tf'   # counts toward devops like the infrastructure files
            if ext:
                counts[ext] = counts.get(ext, 0) + 1
            seen += 1
            if seen >= max_files:
                return counts
    return counts


def detect(path, scan_result=None):
    """{'role', 'confidence', 'roles', 'evidence', 'stacks', 'gaps'} for the project at path (None without one)."""
    if not path or not os.path.isdir(path):
        return None
    counts = count_files(path)
    total = sum(n for e, n in counts.items() if any(e in r[0] for r in ROLES.values())) or 1
    scan_result = scan_result if scan_result is not None else v1.scan_project(path)
    terms = scan_result.get('terms', {})
    score, evidence = {}, {}
    for role, (exts, _tech, _cats) in ROLES.items():
        n = sum(counts.get(e, 0) for e in exts)
        if n:
            score[role] = score.get(role, 0) + n / total
            top = sorted((e for e in exts if counts.get(e)), key=lambda e: -counts[e])[:3]
            evidence.setdefault(role, []).append('%s files' % ', '.join('%d %s' % (counts[e], e) for e in top))
    top_term = max(terms.values()) if terms else 1.0
    for t, w in terms.items():
        role = TECH_ROLE.get(t)
        if role:
            score[role] = score.get(role, 0) + 0.5 * w / top_term
            evidence.setdefault(role, []).append(v1.SHOW.get(t, t))
    if not score:
        return {'role': None, 'confidence': 0.0, 'roles': {}, 'evidence': [], 'stacks': [], 'gaps': []}
    s = sum(score.values())
    roles = {r: round(v / s, 2) for r, v in sorted(score.items(), key=lambda kv: -kv[1])}
    role = next(iter(roles))
    stacks = stacks_of(counts, terms)
    return {'role': role, 'confidence': roles[role], 'roles': roles, 'evidence': evidence.get(role, [])[:5],
            'stacks': stacks, 'gaps': [st for st in stacks if st['skills'] < THIN]}


# Stacks the search cannot see by their own name: the tokenizer drops one-letter words, so C and R are counted by the
# words their skills do use.
COVERAGE_WORDS = {'c': ('cpp', 'firmware', 'embedded', 'microcontroller'), 'r': ('rstats', 'tidyverse', 'ggplot')}


def coverage(word):
    """How many skills name a technology, in their name, description or category."""
    words = COVERAGE_WORDS.get(word.lower(), (word,))
    return len({i for w in words for i in core.POSTINGS.get(core.stem(w.lower()), ())})


def stacks_of(counts, terms):
    """The project's main stacks, each with how many skills cover it."""
    named = {}
    for ext, n in counts.items():
        if ext in STACK_NAMES and n >= 2:
            named[STACK_NAMES[ext]] = named.get(STACK_NAMES[ext], 0) + n
    top_term = max(terms.values()) if terms else 1.0
    for t, w in terms.items():
        if t in v1.TECH_STEMS and w >= 0.3 * top_term:
            name = v1.SHOW.get(t, t)
            named[name] = max(named.get(name, 0), 1)
    out = [{'stack': k, 'files': n, 'skills': coverage(k)} for k, n in named.items()]
    out.sort(key=lambda x: (-x['files'], x['stack']))
    return out[:6]


def role_categories(role):
    return set(ROLES.get(role, ((), '', ()))[2])


def main(argv=None):
    path = (argv or sys.argv[1:] or ['.'])[0]
    print(json.dumps(detect(path), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
