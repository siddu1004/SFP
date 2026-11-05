#!/usr/bin/env python3
"""mcp/sfp_cards.py - Skill cards, task intent extraction, and substitute groups.

Each skill has a card defining its job, output forms, delivery style, depth, needs,
and substitute group.
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CARDS_FILE = os.path.join(ROOT, 'skill_cards.json')

JOBS = ('explain', 'build', 'fix', 'test', 'review', 'design', 'deploy', 'research',
        'write', 'plan', 'automate', 'data', 'secure', 'optimize', 'operate')
OUTPUTS = ('text', 'code', 'diagram', 'animation', 'video', 'slides', 'interactive',
           'audio', 'image', 'document', 'config', 'report')
STYLES = ('step-by-step', 'visual', 'hands-on', 'reference', 'conversational', 'checklist')
DEPTHS = ('beginner', 'practitioner', 'expert')

_CARDS_CACHE = None

def load_cards():
    global _CARDS_CACHE
    if _CARDS_CACHE is not None:
        return _CARDS_CACHE
    cards = {}
    if os.path.isfile(CARDS_FILE):
        try:
            with open(CARDS_FILE, encoding='utf-8') as f:
                cards = json.load(f).get('cards', {})
        except Exception:
            cards = {}
    _CARDS_CACHE = cards
    return cards

def get_card(name):
    cards = load_cards()
    if name in cards:
        return cards[name]
    # Fallback minimal card
    return {
        'job': 'build',
        'output': ['code'],
        'style': 'step-by-step',
        'depth': 'practitioner',
        'needs': [],
        'substitutes_for': 'software-engineering-patterns',
        'source': 'fallback'
    }

def validate_card(c):
    if not isinstance(c, dict):
        return False
    if c.get('job') not in JOBS:
        return False
    outs = c.get('output')
    if not isinstance(outs, list) or not outs or not all(o in OUTPUTS for o in outs):
        return False
    if c.get('style') not in STYLES:
        return False
    if c.get('depth') not in DEPTHS:
        return False
    if not isinstance(c.get('needs'), list):
        return False
    if not c.get('substitutes_for') or not isinstance(c.get('substitutes_for'), str):
        return False
    return True

# Explicit output form patterns in user requests
OUTPUT_PATTERNS = [
    (r'\b(?:animation|animated|animate|manim|motion\s*graphic)\b', 'animation'),
    (r'\b(?:video|screencast|recording|record\s+(?:a\s+)?(?:video|demo|screen|screencast)|movie|clip)\b', 'video'),
    (r'\b(?:slides?|presentation|slide\s*deck|deck|keynote)\b', 'slides'),
    (r'\b(?:diagram|flowchart|mermaid|wireframe)\b', 'diagram'),
    (r'\b(?:interactive|simulator|playground|sandbox)\b', 'interactive'),
    (r'\b(?:(?:generate|create|make|draw|export)\s+(?:an?\s+)?(?:image|picture|graphic|illustration|svg|logo|(?:app\s+)?icon)|as\s+an?\s+image|svg\s+icon)\b', 'image'),
    (r'\b(?:text\s+(?:summary|explanation|breakdown|description|bullet\s+list)|(?:plain|conceptual|brief)\s+text|markdown\s+summary|text\s+only|in\s+(?:plain\s+)?text|in\s+writing|summary\s+of|bullet\s+list|article|essay)\b', 'text'),
    (r'\b(?:as\s+code|code\s+only|boilerplate\s+only|code\s+implementation|code\s+benchmarks?|benchmark\s+code|python\s+tests?|(?:python|go|rust|java|c\+\+|script)\s+code)\b', 'code'),
    (r'\b(?:generate\s+config|write\s+(?:a\s+)?dockerfile|create\s+(?:a\s+)?manifest)\b', 'config'),
    (r'\b(?:report|scorecard|audit\s*summary|audit\s+report|produce\s+an?\s+audit)\b', 'report'),
    (r'\b(?:as\s+a\s+document|draft\s+an?\s+(?:rfc|adr|document|spec)|markdown\s+spec|spec\s+document|release\s+notes|decision\s+records?|adrs?)\b', 'document'),
]

JOB_PATTERNS = [
    (r'\b(?:record|capture|screencast|walkthrough|walk\s+through|showcase|demonstrate|produce|generate|render)\s+.*(?:video|demo|screen|flow|wizard|modal|layout|profile|upload|tour|reel)\b', 'build'),
    (r'\b(?:animated\s+gif|gif\s+showing|slide\s*deck|presentation\s+slide)\b', 'design'),
    (r'\b(?:explain|understand|teach\s+me|what\s+is|show\s+(?:how|visually)|demonstrate\s+visually|illustrat(?:e|ing)|text\s+summary|summary\s+of|comprehensive\s+overview|conceptual\s+text|plain\s+text|visualize|line\s+animation|manim\s+animation|animate\s+the)\b', 'explain'),
    (r'^how\s+(?:to\s+)?(?:distributed|memory|cpu|zero|b-tree|raft|paxos|quicksort|attention|diffusion)\b', 'explain'),
    (r'\b(?:breakdown\s+of)\b', 'explain'),
    (r'\b(?:write\s+(?:a\s+)?(?:[\w-]+\s+){0,2}(?:blog|article|post|changelog|spec\s+document)|draft\s+(?:user[- ]facing\s+)?(?:documentation|doc|rfc|adr|spec)|markdown\s+spec)\b', 'write'),
    (r'\b(?:provide\s+code|code\s+only)\b', 'build'),
    (r'\b(?:write|implement|create|develop|build|scaffold)\s+(?:a\s+|an\s+|the\s+)?(?:python|go|rust|java|c\+\+|cpp|ts|typescript|js|javascript|vue(?:\s+3)?|react|fastapi|swift|modern\s+cpp|idiomatic\s+rust|in-memory|asynchronous|token\s+bucket|trie|jwt|circuit\s+breaker|lsm\s+tree|code|function|functions|composable|middleware|endpoint|class|service|component|pipeline|cache|tree|worker|tool|server|app|interactive\s+playground)\b', 'build'),
    (r'\b(?:tests?|unit\s*tests?|e2e|coverage|assert(?:ion)?s?|benchmarks?)\b', 'test'),
    (r'\b(?:fix|debug|troubleshoot|bug|repair|patch|defect)\b', 'fix'),
    (r'\b(?:review|audit|inspect|lint|check\s+code)\b', 'review'),
    (r'\b(?:secure|security|vulnerability|vulnerabilities|pentest|owasp|hack|hacked|sql\s+injection|xss)\b', 'secure'),
    (r'\b(?:optimize|perf|performance|latency|speed\s+up|re-render|rerender|profile|profiling|bottleneck)\b', 'optimize'),
    (r'\b(?:generate\s+a\s+flowchart|flowchart\s+diagram)\b', 'design'),
    (r'\b(?:build|implement|create|develop|scaffold)\b', 'build'),
    (r'\b(?:design|style|theme|ui|ux|css|palette|layout)\b', 'design'),
    (r'\b(?:deploy|docker|k8s|kubernetes|release|ship|ci/cd)\b', 'deploy'),
    (r'\b(?:research|search|papers?|literature|pubmed|study)\b', 'research'),
    (r'\b(?:doc|docs|article|changelog)\b', 'write'),
    (r'\b(?:plan|roadmap|decision|spec|requirements)\b', 'plan'),
    (r'\b(?:automate|bot|crawler|scrape|workflow)\b', 'automate'),
    (r'\b(?:data|sql|postgres|clickhouse|db|query|database|schema|migrate)\b', 'data'),
    (r'\b(?:operate|ops|monitor|sysadmin|status|health|prometheus|grafana|alert|backup)\b', 'operate'),
    (r'\b(?:explain|summary|summarize|overview|breakdown|explanation)\b', 'explain'),
]

def task_intent(task):
    """Returns (job, named_output_form).
    named_output_form is None if user didn't name a specific medium (e.g. 'explain attention').
    """
    if not task:
        return 'build', None
    low = task.lower()

    # Named output form check
    named_form = None
    for pat, form in OUTPUT_PATTERNS:
        if re.search(pat, low):
            named_form = form
            break

    # Job check
    job = None
    for pat, j in JOB_PATTERNS:
        if re.search(pat, low):
            job = j
            break

    return job, named_form
