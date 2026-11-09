"""Draw the README's animated illustrations, in dark and light themes.

Every number and example comes from the repository itself: the catalog, the newest file in bench/results,
the final exam picks and judgements, and real words-only output from the hive. Run it after a benchmark,
or let scripts/sync.py run it. Writes assets/<name>-dark.svg and assets/<name>-light.svg.

Animations are CSS and SMIL inside each SVG, so they play on GitHub. Each drawing is complete when
animation is off, and `prefers-reduced-motion: reduce` turns all motion off.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assets')

FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

THEMES = {
    'dark': {'bg': '#12171f', 'tile': '#18202b', 'grid': '#2c3643', 'ink': '#e6edf3', 'ink2': '#9aa4b0',
             'muted': '#4a5768', 'accent': '#2dd4bf', 'on_accent': '#06201d', 'term': '#0b0f15',
             'teal': '#2dd4bf', 'amber': '#fbbf24', 'violet': '#a78bfa', 'rose': '#fb7185',
             'sky': '#38bdf8', 'lime': '#a3e635', 'soft': 0.22},
    'light': {'bg': '#f4f1ea', 'tile': '#fbf9f4', 'grid': '#e2ddd2', 'ink': '#1a1d21', 'ink2': '#565c64',
              'muted': '#a8a190', 'accent': '#0f766e', 'on_accent': '#ffffff', 'term': '#1a1d21',
              'teal': '#0f766e', 'amber': '#b45309', 'violet': '#6d28d9', 'rose': '#be123c',
              'sky': '#0369a1', 'lime': '#4d7c0f', 'soft': 0.16},
}
COLORS = ['teal', 'violet', 'amber', 'rose', 'sky', 'lime']

# Category families for the library map and the role cards. Categories not listed fall into "More".
FAMILIES = [
    ('AI agents and MCP', 'violet', ['agents', 'agent-dev', 'ai-gateway', 'ai-ml', 'memory']),
    ('Business and content', 'amber', ['business-ops', 'content-media', 'career', 'industry']),
    ('Science and research', 'lime', ['science-hardware', 'research-docs']),
    ('Design and frontend', 'rose', ['frontend', 'design-styles']),
    ('Engineering', 'sky', ['backend', 'engineering', 'devops', 'mobile', 'languages', 'networking',
                            'data-apis', 'web3']),
    ('Testing and security', 'teal', ['testing-quality', 'security', 'sfp']),
]

TOOLS = ['Claude Code', 'Codex', 'Cursor', 'Gemini CLI', 'Antigravity', 'GitHub Copilot', 'VS Code',
         'Windsurf', 'Kiro', 'OpenCode', 'Cline', 'Roo Code', 'Trae', 'Qoder', 'Pi', 'Grok Build',
         'Rovo Dev', 'Mistral Vibe', 'Hermes', 'Any MCP client']

BASE_CSS = """
text{font-family:%(font)s}
.mono{font-family:%(mono)s}
.draw{stroke-dasharray:1;stroke-dashoffset:0;animation:draw 1.1s cubic-bezier(.23,1,.32,1) both}
.rise{animation:rise .7s cubic-bezier(.23,1,.32,1) both}
.fade{animation:fade .8s ease-out both}
.grow{transform-box:fill-box;transform-origin:left center;animation:grow 1.1s cubic-bezier(.23,1,.32,1) both}
.pop{transform-box:fill-box;transform-origin:center;animation:pop .5s cubic-bezier(.23,1,.32,1) both}
.glow{animation:glow 2.6s ease-in-out infinite}
.blink{animation:blink 1s steps(1) infinite}
@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes pop{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:scale(1)}}
@keyframes glow{0%%,100%%{opacity:.45}50%%{opacity:1}}
@keyframes blink{0%%{opacity:1}50%%{opacity:0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}.pulse,.cover{display:none}}
""" % {'font': FONT, 'mono': MONO}


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def d(delay):
    return f' style="animation-delay:{delay:.2f}s"'


def text(x, y, s, size, fill, weight=400, anchor='start', cls='', extra=''):
    c = f' class="{cls}"' if cls else ''
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{c}{extra}>{esc(s)}</text>')


def width(s, size, mono=False):
    return len(s) * size * (0.6 if mono else 0.56)


def svg(w, h, title, desc, body, t):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="t d"><title id="t">{esc(title)}</title><desc id="d">{esc(desc)}</desc>'
            f'<style>{BASE_CSS}</style><rect width="{w}" height="{h}" rx="16" fill="{t["bg"]}"/>{body}</svg>')


def pulse(path, color, begin, dur=2.4):
    return (f'<circle class="pulse" r="4" fill="{color}" opacity="0"><animateMotion path="{path}" '
            f'dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/><animate attributeName="opacity" '
            f'values="0;1;1;0" keyTimes="0;.1;.85;1" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
            f'</circle>')


def header(t, title, sub, x=40):
    return text(x, 50, title, 26, t['ink'], 700, cls='rise') + text(x, 80, sub, 16, t['ink2'], cls='rise',
                                                                     extra=d(.1))


# ----------------------------------------------------------------- data


def load_catalog():
    c = json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))
    return c['skills'] if isinstance(c, dict) else c


def latest_results():
    files = sorted(glob.glob(os.path.join(ROOT, 'bench', 'results', '*.json')))
    return json.load(open(files[-1], encoding='utf-8')) if files else None


def design_numbers():
    runs = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'bench', 'design', 'results', '*.json'))):
        with open(f, encoding='utf-8') as fh:
            runs += json.load(fh)
    out = {}
    for arm in ('baseline', 'sfp', 'picked'):
        xs = [r for r in runs if r['arm'] == arm]
        if xs:
            out[arm] = {'n': len(xs), 'shipped': sum(1 for r in xs if r['rounds_to_ship']),
                        'rounds': sum((r['rounds_to_ship'] or 5) for r in xs) / len(xs)}
    return out


def exam_scores():
    """Both scoreboards for the final exam, from the saved picks: the original labels, and the blind pooled judge."""
    picks_path = os.path.join(ROOT, 'bench', 'exam_picks.json')
    judged_path = os.path.join(ROOT, 'tests', 'exam_judged.json')
    if not (os.path.isfile(picks_path) and os.path.isfile(judged_path)):
        return None
    picks = json.load(open(picks_path, encoding='utf-8'))
    judged = json.load(open(judged_path, encoding='utf-8'))
    expect = {}
    for name in ('exam_plain', 'exam_project', 'exam_reworded'):
        data = json.load(open(os.path.join(ROOT, 'tests', name + '.json'), encoding='utf-8'))
        for case in (data if isinstance(data, list) else data.get('cases', [])):
            expect[case['task']] = set(case.get('expect', []))
    agg = defaultdict(Counter)
    for row in picks:
        task, engine, chosen = row['task'], row['engine'], row['picks']
        ok = judged.get(task, {})
        exp = expect.get(task, set())
        a = agg[engine]
        a['n'] += 1
        a['judge_chosen'] += any(ok.get(p) or p in exp for p in chosen)
        a['judge_first'] += bool(chosen) and bool(ok.get(chosen[0]) or chosen[0] in exp)
        a['label_chosen'] += bool(set(chosen) & exp)
        a['label_first'] += bool(chosen) and chosen[0] in exp
    out = {}
    for e, a in agg.items():
        out[e] = {k: round(100 * v / a['n']) for k, v in a.items() if k != 'n'}
        out[e]['n'] = a['n']
    return out


def hive(task):
    """Real words-only output from the hive, in a throwaway data folder, so it is the same on every machine."""
    env = dict(os.environ, SFP_SEMANTIC='0', SFP_RERANK='0', SFP_EXPAND='0',
               SFP_DATA_DIR=tempfile.mkdtemp(prefix='sfp-art-'))
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'mcp', 'sfp_hive.py'), 'select', task, '--json'],
                         capture_output=True, text=True, encoding='utf-8', env=env, cwd=ROOT, timeout=120)
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {}


# ----------------------------------------------------------------- drawings


def hero(t, total, ncats, example):
    """Unified animated banner at the top of the README: wordmark, domain pills, animated shelf and live stack."""
    task = example['task']
    stack = [s['name'] for s in example.get('stack', [])][:3] or ['web-app-penetration-testing', 'security-review']
    body = [f'<defs><radialGradient id="g" cx="76%" cy="46%" r="54%"><stop offset="0" stop-color="{t["accent"]}" '
            f'stop-opacity="{t["soft"]}"/><stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/>'
            f'</radialGradient></defs><rect width="1280" height="360" rx="16" fill="url(#g)"/>']
    body.append(text(56, 76, 'SKILLS FOR PRODUCTIVITY', 13, t['accent'], 700, cls='rise',
                     extra=' letter-spacing="3"'))
    body.append(text(52, 172, 'SFP', 108, t['ink'], 800, cls='rise', extra=d(.08) + ' letter-spacing="-4"'))
    body.append(text(56, 218, f'{total:,} specialist skills across {ncats} categories.', 24, t['ink'], 700, cls='rise', extra=d(.16)))
    body.append(text(56, 250, 'SFP reads your task & project, then loads only the 1 to 3 you need.', 17, t['ink2'], 500, cls='rise', extra=d(.22)))

    # Six domain pills (two neat rows of three) so they complement rather than repeat the shields.io badges below.
    domains = [
        ('AI & MCP', 'violet'),
        ('UI & Design', 'rose'),
        ('Engineering', 'sky'),
        ('Business & Growth', 'amber'),
        ('Testing & Security', 'teal'),
        ('Science & Docs', 'lime'),
    ]
    for i, (label, col) in enumerate(domains):
        row_i, col_i = divmod(i, 3)
        px = 56 + col_i * 172
        py = 274 + row_i * 34
        c = t[col]
        body.append(f'<g class="rise"{d(.32 + i * .06)}><rect x="{px}" y="{py}" width="162" height="26" rx="13" '
                    f'fill="{t["tile"]}" stroke="{c}" stroke-width="1.5"/>'
                    f'<circle cx="{px + 15}" cy="{py + 13}" r="4" fill="{c}"/>'
                    + text(px + 26, py + 17, label, 12, t['ink'], 600) + '</g>')

    # The shelf: one tile per group of skills, coloured by family.
    gx, gy, cols, rows, size, gap = 620, 74, 10, 7, 28, 8
    lit = [(1, 6), (3, 2), (5, 7)][:len(stack)]
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            x0, y0 = gx + c * (size + gap), gy + r * (size + gap)
            color = t[COLORS[(c * 7 + r * 3) % len(COLORS)]]
            body.append(f'<rect class="pop" x="{x0}" y="{y0}" width="{size}" height="{size}" rx="6" fill="{color}" '
                        f'fill-opacity="{t["soft"]}"{d(.18 + i * .005)}/>')
    # The task, the lines to the chosen tiles, and the stack.
    cw = width(task, 14) + 36
    body.append(f'<g class="rise"{d(.45)}><rect x="{gx}" y="24" width="{cw:.0f}" height="34" rx="17" fill="{t["tile"]}" '
                f'stroke="{t["grid"]}" stroke-width="1.5"/>' + text(gx + 18, 46, f'Task: "{task}"', 13, t['ink'], 600) + '</g>')
    card_x, card_y = 1012, 114
    body.append(f'<g class="rise"{d(1.4)}><rect x="{card_x}" y="{card_y}" width="238" height="{64 + 38 * len(stack)}" '
                f'rx="12" fill="{t["tile"]}" stroke="{t["accent"]}" stroke-width="2"/>'
                + text(card_x + 18, card_y + 30, 'Picked for this task', 14, t['ink'], 700)
                + text(card_x + 18, card_y + 46, '96% context saved', 11, t['accent'], 600) + '</g>')
    for i, (r, c) in enumerate(lit):
        cx, cy = gx + c * (size + gap) + size / 2, gy + r * (size + gap) + size / 2
        ry = card_y + 72 + 38 * i
        p1 = f'M{gx + 40} 58 C{gx + 40} {cy - 36} {cx - 60} {cy} {cx - size / 2} {cy}'
        p2 = f'M{cx + size / 2} {cy} C{cx + 90} {cy} {card_x - 70} {ry} {card_x} {ry}'
        for k, p in enumerate((p1, p2)):
            body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{t["accent"]}" '
                        f'stroke-width="2" stroke-linecap="round"{d(.7 + .45 * k + .15 * i)}/>')
        body.append(f'<rect class="glow" x="{cx - size / 2 - 3}" y="{cy - size / 2 - 3}" width="{size + 6}" '
                    f'height="{size + 6}" rx="8" fill="{t["accent"]}"/>')
        body.append(pulse(p2, t['accent'], 2.0 + .4 * i))
        label_name = stack[i] if len(stack[i]) <= 24 else stack[i][:22] + '..'
        body.append(f'<g class="rise"{d(1.6 + .15 * i)}><circle cx="{card_x + 26}" cy="{ry - 4}" r="10" fill="{t["accent"]}"/>'
                    + text(card_x + 26, ry, str(i + 1), 11, t['on_accent'], 700, 'middle')
                    + text(card_x + 42, ry, label_name, 12, t['ink'], 600, cls='mono') + '</g>')
    desc = (f'SFP keeps {total:,} skills on a shelf across {ncats} categories. For the task "{task}" it lights up '
            f'the few that fit and hands them to your AI: {", ".join(stack)}.')
    return svg(1280, 360, 'SFP: Skills for Productivity', desc, ''.join(body), t)


def pipeline(t):
    body = [header(t, 'How SFP picks', 'Everything runs on your machine. Dashed steps are optional and use a local model.')]
    nodes = [  # x, y, w, title, lines, dashed, color
        (40, 200, 150, 'Your task', ['what you asked,', 'and your project'], False, 'ink2'),
        (250, 140, 170, 'Words', ['matching words in', 'names and examples'], False, 'sky'),
        (250, 230, 170, 'Meaning', ['a local embedding', 'model (bge-m3)'], True, 'violet'),
        (250, 320, 170, 'Project fit', ['drops skills for', 'other technologies'], False, 'amber'),
        (480, 230, 150, 'Fuse', ['rank fusion,', 'one shortlist'], False, 'teal'),
        (670, 230, 150, 'Local judge', ['a chat model', 'orders the list'], True, 'rose'),
        (860, 230, 110, 'Your stack', ['1 to 3 skills,', 'plus bundles'], False, 'teal'),
    ]
    centers = {}
    for i, (x, y, w, title, lines, dashed, col) in enumerate(nodes):
        h = 74
        dash = ' stroke-dasharray="6 5"' if dashed else ''
        stroke = t[col] if col != 'ink2' else t['grid']
        top = y - h / 2
        body.append(f'<g class="rise"{d(.2 + .12 * i)}><rect x="{x}" y="{top}" width="{w}" height="{h}" rx="12" '
                    f'fill="{t["tile"]}" stroke="{stroke}" stroke-width="2"{dash}/>'
                    f'<rect x="{x}" y="{top + 14}" width="4" height="{h - 28}" rx="2" fill="{stroke}"/>'
                    + text(x + 16, top + 26, title, 16, t['ink'], 700)
                    + text(x + 16, top + 46, lines[0], 13, t['ink2'])
                    + text(x + 16, top + 63, lines[1], 13, t['ink2']) + '</g>')
        centers[title] = (x, y, w)

    def link(a, b, delay, color=None):
        ax, ay, aw = centers[a]
        bx, by, _ = centers[b]
        x1, x2 = ax + aw, bx
        mid = (x1 + x2) / 2
        p = f'M{x1} {ay} C{mid} {ay} {mid} {by} {x2 - 6} {by}'
        c = color or t['accent']
        return (f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="2" '
                f'stroke-linecap="round"{d(delay)}/><path class="fade" d="M{x2} {by} l-9 -5 v10 z" fill="{c}"{d(delay + .8)}/>',
                p)

    paths = []
    for i, (a, b) in enumerate([('Your task', 'Words'), ('Your task', 'Meaning'), ('Your task', 'Project fit'),
                                ('Words', 'Fuse'), ('Meaning', 'Fuse'), ('Project fit', 'Fuse'),
                                ('Fuse', 'Local judge'), ('Local judge', 'Your stack')]):
        s, p = link(a, b, 1.0 + .18 * i)
        body.append(s)
        paths.append(p)
    for i, p in enumerate(paths):
        body.append(pulse(p, t['accent'], 2.6 + .3 * (i % 4), 2.0))
    # The feedback loop.
    loop = 'M915 267 V382 H555 V267'
    body.append(f'<path class="draw" pathLength="1" d="{loop}" fill="none" stroke="{t["accent"]}" stroke-width="2" '
                f'stroke-dasharray="1"{d(2.6)}/>')
    body.append(f'<path class="fade" d="M555 269 l-5 9 h10 z" fill="{t["accent"]}"{d(3.2)}/>')
    body.append(f'<rect x="600" y="370" width="270" height="24" fill="{t["bg"]}"/>')
    body.append(text(735, 387, 'learns from "helped" and "did not help"', 13, t['accent'], 600, 'middle', 'fade', d(3.0)))
    desc = ('Your task and project go to three signals: words, meaning and project fit. Rank fusion joins them into '
            'one shortlist, an optional local model orders it, and you get one to three skills plus fitting bundles. '
            'Your feedback flows back into the choice.')
    return svg(1000, 410, 'How SFP picks', desc, ''.join(body), t)


def advantages(t, total):
    """Six animated bento cards showing the core architectural advantages of SFP."""
    body = [header(t, 'Why teams switch to SFP',
                   'Eliminates context bloat (loading 50+ rules) and context starvation (guessing conventions).')]
    cards = [
        ('96% Less Context', 'teal', '3,383 vs 81,691 tokens',
         'Loads only the 1 to 3 skills needed right now,', 'leaving 98% of your 200k window free for code.'),
        ('Manifest Stack Fit', 'sky', '0 wrong-tech picks',
         'Inspects package.json, Cargo.toml and go.mod', 'so Go never gets Django rules and Rust stays Rust.'),
        ('0.0% Junk Rate', 'violet', 'Strict confidence gating',
         'Micro-edits and negative edge tasks return clean', 'empty stacks instead of 62% keyword noise.'),
        ('Adaptive Taste', 'rose', '100% format override',
         'Learns whether you prefer code, prose, motion', 'or video over a 30-day feedback half-life.'),
        ('100% Local & Private', 'amber', '~3 ms words-only pick',
         'Runs in stdlib Python on your machine. Optional', 'Ollama / LM Studio models keep prompts local.'),
        ('20 AI Tools Synced', 'lime', f'{total:,} skills everywhere',
         'Claude Code, Cursor, Antigravity, Copilot, Codex,', 'Windsurf and any MCP client share one brain.'),
    ]
    cw, ch = 295, 148
    for i, (title, col, badge, line1, line2) in enumerate(cards):
        x, y = 40 + (i % 3) * (cw + 17.5), 108 + (i // 3) * (ch + 18)
        c = t[col]
        bw = width(badge, 12, True) + 20
        body.append(
            f'<g class="rise"{d(.18 + .1 * i)}>'
            f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="14" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
            f'<path class="draw" pathLength="1" d="M{x + 14} {y + 1} H{x + cw - 14}" stroke="{c}" stroke-width="4" stroke-linecap="round" fill="none"{d(.45 + .1 * i)}/>'
            f'<rect x="{x + 18}" y="{y + 20}" width="{bw:.0f}" height="24" rx="12" fill="{c}" fill-opacity="{t["soft"]}"/>'
            + text(x + 28, y + 36, badge, 12, c, 700, cls='mono')
            + text(x + 18, y + 70, title, 18, t['ink'], 700)
            + text(x + 18, y + 98, line1, 13, t['ink2'])
            + text(x + 18, y + 118, line2, 13, t['ink2'])
            + '</g>'
        )
    desc = 'Six unfair advantages of SFP: 96% less context, manifest stack fit, 0.0% junk rate, adaptive taste, 100% local and private execution, and 20 AI tools synced.'
    return svg(1000, 444, 'Why SFP: The Unfair Advantages', desc, ''.join(body), t)


def project_fit(t):
    """Animated branching diagram: one prompt routes to 5 distinct project stacks based on root manifests."""
    body = [header(t, 'Same words, five projects, zero cross-contamination',
                   'Keyword search returns the same generic list every time. SFP inspects your project manifest first.')]
    # Left prompt box
    body.append(
        f'<g class="rise"{d(.15)}>'
        f'<rect x="40" y="186" width="210" height="84" rx="12" fill="{t["tile"]}" stroke="{t["accent"]}" stroke-width="2"/>'
        + text(58, 216, 'Your prompt', 13, t['accent'], 700)
        + text(58, 240, '"write tests for', 15, t['ink'], 700, cls='mono')
        + text(58, 258, ' the orders"', 15, t['ink'], 700, cls='mono')
        + '</g>'
    )
    # Center Hive node
    body.append(
        f'<g class="rise"{d(.35)}>'
        f'<rect x="300" y="176" width="156" height="104" rx="14" fill="{t["tile"]}" stroke="{t["teal"]}" stroke-width="2"/>'
        + text(378, 212, 'SFP Hive', 17, t['ink'], 700, 'middle')
        + text(378, 234, 'Reads manifest', 13, t['ink2'], 500, 'middle')
        + text(378, 254, '+ filters stack', 13, t['teal'], 600, 'middle')
        + '</g>'
    )
    p_in = 'M250 228 H294'
    body.append(f'<path class="draw" pathLength="1" d="{p_in}" fill="none" stroke="{t["accent"]}" stroke-width="2"{d(.5)}/>'
                f'<path class="fade" d="M300 228 l-8 -4 v8 z" fill="{t["accent"]}"{d(.9)}/>')
    body.append(pulse(p_in, t['accent'], 1.2, 1.6))

    targets = [
        ('Next.js', 'package.json', 'sky', 'e2e-testing, react-testing, typescript-Write-Tests'),
        ('Rust', 'Cargo.toml', 'amber', 'rust-testing, test-collaboration'),
        ('.NET', '*.csproj', 'violet', 'csharp-testing, fsharp-testing, tdd-workflow'),
        ('Flutter', 'pubspec.yaml', 'teal', 'dart-flutter-patterns, flutter-dart-code-review'),
        ('Django', 'manage.py', 'lime', 'django-tdd, python-testing, tdd-workflow'),
    ]
    for i, (proj, manifest, col, picks) in enumerate(targets):
        ry = 122 + i * 54
        c = t[col]
        p = f'M456 228 C500 228 500 {ry} 544 {ry}'
        body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="2"{d(.65 + .12 * i)}/>'
                    f'<path class="fade" d="M550 {ry} l-8 -4 v8 z" fill="{c}"{d(1.1 + .12 * i)}/>')
        body.append(pulse(p, c, 1.5 + .28 * i, 2.0))
        body.append(
            f'<g class="rise"{d(.75 + .12 * i)}>'
            f'<rect x="552" y="{ry - 21}" width="408" height="42" rx="10" fill="{t["tile"]}" stroke="{c}" stroke-width="1.5"/>'
            f'<rect x="562" y="{ry - 13}" width="132" height="26" rx="6" fill="{c}" fill-opacity="{t["soft"]}"/>'
            + text(572, ry + 4, f'{proj} ({manifest})', 12, t['ink'], 700)
            + text(706, ry + 4, picks, 12, t['ink'], 500, cls='mono')
            + '</g>'
        )
    desc = ('For the prompt "write tests for the orders", SFP inspects the project manifest and chooses '
            'Next.js -> e2e-testing/react-testing, Rust -> rust-testing, .NET -> csharp-testing, '
            'Flutter -> dart-flutter-patterns, Django -> django-tdd.')
    return svg(1000, 396, 'Same words across five projects', desc, ''.join(body), t)


def taste(t):
    """Animated dual-panel illustration: Persona Format Adaptation (left) + Autonomous Research Mentor (right)."""
    body = [header(t, 'It learns your taste and grows missing skills',
                   'Tracks format preferences with a 30-day half-life, and drafts new skills from peer-reviewed papers.')]
    # Left panel: Format adaptation across 4 learner personas
    body.append(
        f'<g class="rise"{d(.15)}>'
        f'<rect x="40" y="106" width="450" height="296" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
        + text(60, 138, '1. Format Adaptation by Learner Persona', 17, t['ink'], 700)
        + text(60, 158, 'First pick matches preferred format (40 unseen tasks)', 12, t['ink2'])
        + f'<rect x="60" y="172" width="12" height="10" rx="3" fill="{t["muted"]}"/>'
        + text(78, 181, 'Cold start', 12, t['ink2'])
        + f'<rect x="164" y="172" width="12" height="10" rx="3" fill="{t["accent"]}"/>'
        + text(182, 181, 'After learning taste', 12, t['ink'], 600)
        + '</g>'
    )
    personas = [
        ('Visual (Animation)', 'violet', 40, 80),
        ('Reader (Deep Text)', 'sky', 70, 100),
        ('Hands-on (Code)', 'teal', 80, 100),
        ('Producer (Video)', 'amber', 90, 100),
    ]
    for i, (label, col, cold, warm) in enumerate(personas):
        y = 202 + i * 42
        c = t[col]
        bw = 210
        body.append(text(60, y + 14, label, 13, t['ink'], 600, cls='fade', extra=d(.3 + .1 * i)))
        body.append(f'<rect class="grow" x="205" y="{y - 2}" width="{bw * cold / 100:.1f}" height="10" rx="3" fill="{t["muted"]}"{d(.45 + .1 * i)}/>')
        body.append(f'<rect class="grow" x="205" y="{y + 11}" width="{bw * warm / 100:.1f}" height="12" rx="3" fill="{c}"{d(.65 + .1 * i)}/>')
        body.append(text(205 + bw * warm / 100 + 8, y + 21, f'{cold}% -> {warm}%', 12, t['ink'], 700, cls='mono fade', extra=d(.95 + .1 * i)))
    body.append(
        f'<g class="rise"{d(1.1)}>'
        f'<rect x="60" y="366" width="410" height="24" rx="6" fill="{t["accent"]}" fill-opacity="{t["soft"]}"/>'
        + text(265, 382, '100% strict compliance when prompt names a format ("as text")', 12, t['accent'], 700, 'middle')
        + '</g>'
    )

    # Right panel: The Autonomous Research Mentor pipeline
    body.append(
        f'<g class="rise"{d(.25)}>'
        f'<rect x="510" y="106" width="450" height="296" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
        + text(530, 138, '2. Autonomous Research Mentor', 17, t['ink'], 700)
        + text(530, 158, 'Fills library gaps from OpenAlex, arXiv & Semantic Scholar', 12, t['ink2'])
        + '</g>'
    )
    msteps = [
        ('1. Detect Gap', 'sfp mentor spots thin stack coverage', 'rose'),
        ('2. Fetch Papers', 'Well-cited works from OpenAlex & arXiv', 'sky'),
        ('3. Draft Skill', 'Local model distills methods into SKILL.md', 'violet'),
        ('4. You Approve', 'sfp research approve <name> installs it', 'teal'),
    ]
    for i, (st, sub, col) in enumerate(msteps):
        sy = 178 + i * 52
        c = t[col]
        body.append(
            f'<g class="rise"{d(.4 + .15 * i)}>'
            f'<rect x="530" y="{sy}" width="410" height="40" rx="8" fill="{t["bg"]}" stroke="{c}" stroke-width="1.5"/>'
            + text(546, sy + 18, st, 13, c, 700, cls='mono')
            + text(546, sy + 33, sub, 12, t['ink2'])
            + '</g>'
        )
        if i < len(msteps) - 1:
            p = f'M735 {sy + 40} V{sy + 52}'
            body.append(f'<path class="draw" pathLength="1" d="{p}" stroke="{c}" stroke-width="2" fill="none"{d(.7 + .15 * i)}/>')
            body.append(pulse(p, c, 1.4 + .3 * i, 1.6))

    desc = ('SFP learns which format helps you across animation, reading, code and video, respecting explicit format '
            'overrides 100% of the time, while the research mentor turns academic papers into draft skills for your approval.')
    return svg(1000, 424, 'How SFP learns your taste and grows skills', desc, ''.join(body), t)


def plain_words(t):
    """Animated dual-panel illustration: Local Model Accuracy Lift (left) + Plain-Words Semantic Bridge (right)."""
    body = [header(t, 'When you describe the problem in plain words',
                   'Add a free local embedding model (bge-m3) and chat judge to understand intent, not just keywords.')]
    # Left panel: Paraphrased / Reworded Benchmark Lift
    body.append(
        f'<g class="rise"{d(.15)}>'
        f'<rect x="40" y="106" width="440" height="276" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
        + text(60, 138, 'Paraphrased Tasks (Zero Shared Keywords)', 17, t['ink'], 700)
        + text(60, 158, 'Right skill chosen when phrasing is reworded', 12, t['ink2'])
        + '</g>'
    )
    bars = [
        ('Keyword search', 57, 'muted', '57%'),
        ('SFP words only', 57, 'sky', '57% (0% junk)'),
        ('+ Meaning (bge-m3)', 77, 'violet', '77% (+20 pts)'),
        ('+ Local model judge', 83, 'teal', '83% (97% on final exam)'),
    ]
    for i, (label, val, col, note) in enumerate(bars):
        y = 184 + i * 46
        c = t[col]
        bw = 175
        body.append(text(60, y + 15, label, 13, t['ink'] if col == 'teal' else t['ink2'], 700 if col == 'teal' else 500, cls='fade', extra=d(.3 + .1 * i)))
        body.append(f'<rect x="200" y="{y}" width="{bw}" height="20" rx="5" fill="{t["grid"]}" fill-opacity=".5"/>')
        body.append(f'<rect class="grow" x="200" y="{y}" width="{bw * val / 100:.1f}" height="20" rx="5" fill="{c}"{d(.5 + .14 * i)}/>')
        body.append(text(200 + bw + 10, y + 15, note, 12, t['ink'] if col == 'teal' else t['ink2'], 700 if col == 'teal' else 500, cls='fade', extra=d(.9 + .1 * i)))

    # Right panel: Live Semantic Translation Bridge
    body.append(
        f'<g class="rise"{d(.25)}>'
        f'<rect x="500" y="106" width="460" height="276" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
        + text(520, 138, 'How Plain English Maps to Specialist Skills', 17, t['ink'], 700)
        + text(520, 158, 'bge-m3 cosine similarity + local chat model rerank', 12, t['ink2'])
        + '</g>'
    )
    examples = [
        ('"make the login not get hacked"', 'security-review', 'teal'),
        ('"test all the buttons on my site"', 'playwright-cli', 'violet'),
        ('"sneaky memory leaks in goroutines"', 'golang-patterns', 'amber'),
        ('"explain attention visually"', 'manim-video', 'rose'),
    ]
    for i, (ask, picked, col) in enumerate(examples):
        y = 184 + i * 46
        c = t[col]
        body.append(
            f'<g class="rise"{d(.45 + .14 * i)}>'
            f'<rect x="520" y="{y - 4}" width="228" height="30" rx="7" fill="{t["bg"]}" stroke="{t["grid"]}" stroke-width="1"/>'
            + text(530, y + 15, ask, 12, t['ink2'])
            + f'<rect x="782" y="{y - 4}" width="158" height="30" rx="7" fill="{c}" fill-opacity="{t["soft"]}" stroke="{c}" stroke-width="1.5"/>'
            + text(861, y + 15, picked, 12, t['ink'], 700, 'middle', cls='mono')
            + '</g>'
        )
        p = f'M748 {y + 11} H776'
        body.append(f'<path class="draw" pathLength="1" d="{p}" stroke="{c}" stroke-width="2" fill="none"{d(.7 + .14 * i)}/>'
                    f'<path class="fade" d="M780 {y + 11} l-6 -4 v8 z" fill="{c}"{d(1.0 + .14 * i)}/>')
        body.append(pulse(p, c, 1.5 + .3 * i, 1.8))

    desc = ('Adding a local embedding model (bge-m3) and chat judge raises accuracy on paraphrased tasks from 57% to 83% '
            '(and 97% on the 150-task final exam), mapping beginner prompts directly to specialist skills.')
    return svg(1000, 404, 'Understanding plain words with local models', desc, ''.join(body), t)


def exam(t, scores):
    engines = [('3.20.0', 'SFP 3.20', 'accent'), ('keyword', 'Keyword search', 'muted'), ('v3.19.0', 'SFP 3.19', 'muted')]
    n = max(v['n'] for v in scores.values())
    body = [header(t, f'Final exam: {n} new tasks',
                   'Written after the work was done, scored once. Thick bar: right skill first. Thin bar: right skill anywhere in the stack.')]
    panels = [('judge', 'Blind judge', 'A local model rated every pick without knowing the engine'),
              ('label', 'Original labels', 'Only the skills named when each task was written')]
    for p, (key, title, sub) in enumerate(panels):
        px = 40 + p * 470
        body.append(f'<g class="rise"{d(.2 + .1 * p)}><rect x="{px}" y="108" width="450" height="272" rx="12" '
                    f'fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
                    + text(px + 20, 140, title, 18, t['ink'], 700) + text(px + 20, 162, sub, 13, t['ink2']) + '</g>')
        for i, (eng, label, col) in enumerate(engines):
            s = scores.get(eng)
            if not s:
                continue
            y = 200 + i * 60
            first, chosen = s[key + '_first'], s[key + '_chosen']
            bw = 250
            color = t[col]
            body.append(text(px + 20, y + 14, label, 14, t['ink'] if col == 'accent' else t['ink2'],
                             700 if col == 'accent' else 500, cls='fade', extra=d(.4)))
            body.append(f'<rect x="{px + 140}" y="{y}" width="{bw}" height="18" rx="4" fill="{t["grid"]}" fill-opacity=".6"/>')
            body.append(f'<rect class="grow" x="{px + 140}" y="{y}" width="{bw * first / 100:.1f}" height="18" rx="4" '
                        f'fill="{color}"{d(.6 + .15 * i + .1 * p)}/>')
            body.append(f'<rect class="grow" x="{px + 140}" y="{y + 24}" width="{bw * chosen / 100:.1f}" height="5" rx="2.5" '
                        f'fill="{color}" fill-opacity=".55"{d(.8 + .15 * i + .1 * p)}/>')
            body.append(text(px + 140 + bw + 10, y + 15, f'{first}%', 15, t['ink'], 700, cls='fade', extra=d(1.4)))
            body.append(text(px + 140 + bw + 10, y + 31, f'{chosen}% in stack', 11, t['ink2'], cls='fade', extra=d(1.5)))
    body.append(text(40, 402, 'The judge is generous and the labels are narrow: the truth is between them. '
                              'Method and every set: bench/RESULTS.md.', 13, t['ink2'], cls='fade', extra=d(1.6)))
    s = scores.get('3.20.0', {})
    desc = (f'On {n} new tasks, SFP 3.20 put the right skill first {s.get("judge_first")}% of the time by the blind judge '
            f'and {s.get("label_first")}% by the original labels, against {scores.get("keyword", {}).get("judge_first")}% '
            f'and {scores.get("keyword", {}).get("label_first")}% for keyword search and '
            f'{scores.get("v3.19.0", {}).get("judge_first")}% and {scores.get("v3.19.0", {}).get("label_first")}% for SFP 3.19.')
    return svg(1000, 420, 'Final exam results', desc, ''.join(body), t)


def results_rounds(t, dz):
    """Animated dual-panel illustration: Blind UI Design Review Rounds (left) + Unseen Tool Verification Checks (right)."""
    sfp_r = dz.get('sfp', {}).get('rounds', 2.8)
    pick_r = dz.get('picked', {}).get('rounds', 3.4)
    base_r = dz.get('baseline', {}).get('rounds', 3.7)
    sfp_s = dz.get('sfp', {}).get('shipped', 8)
    sfp_n = dz.get('sfp', {}).get('n', 9)
    pick_s = dz.get('picked', {}).get('shipped', 6)
    base_s = dz.get('baseline', {}).get('shipped', 5)

    body = [header(t, 'Does it make the agent’s output better?',
                   'Blind design reviews and unseen CLI verification checks (docs/EFFECT.md).')]
    # Left panel: Design review rounds
    body.append(
        f'<g class="rise"{d(.15)}>'
        f'<rect x="40" y="106" width="450" height="246" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
        + text(60, 138, '1. Blind UI Design Reviews (Lower is Better)', 17, t['ink'], 700)
        + text(60, 158, 'Review rounds until a blind judge accepts the page', 12, t['ink2'])
        + '</g>'
    )
    rows = [
        ('SFP picks skills', sfp_r, 'teal', f'{sfp_r:.1f} rounds ({sfp_s}/{sfp_n} shipped)'),
        ('Hand-picked skills', pick_r, 'violet', f'{pick_r:.1f} rounds ({pick_s}/{sfp_n} shipped)'),
        ('No skills', base_r, 'rose', f'{base_r:.1f} rounds ({base_s}/{sfp_n} shipped)'),
    ]
    for i, (label, val, col, note) in enumerate(rows):
        y = 186 + i * 50
        c = t[col]
        bw = 160
        body.append(text(60, y + 16, label, 13, t['ink'] if col == 'teal' else t['ink2'], 700 if col == 'teal' else 500, cls='fade', extra=d(.3 + .1 * i)))
        body.append(f'<rect x="195" y="{y}" width="{bw}" height="22" rx="5" fill="{t["grid"]}" fill-opacity=".5"/>')
        body.append(f'<rect class="grow" x="195" y="{y}" width="{bw * val / 5.0:.1f}" height="22" rx="5" fill="{c}"{d(.5 + .15 * i)}/>')
        body.append(text(195 + bw + 10, y + 16, note, 12, t['ink'] if col == 'teal' else t['ink2'], 700 if col == 'teal' else 500, cls='fade', extra=d(.9 + .1 * i)))

    # Right panel: Unseen tool verification (7 checks)
    body.append(
        f'<g class="rise"{d(.25)}>'
        f'<rect x="510" y="106" width="450" height="246" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
        + text(530, 138, '2. Unseen Tool Benchmark (7 Checks)', 17, t['ink'], 700)
        + text(530, 158, 'Agent given a CLI/API tool not in its training weights', 12, t['ink2'])
        + '</g>'
    )
    # Row A: With SFP (7/7 green check circles)
    body.append(text(530, 204, 'With SFP skill loaded', 14, t['ink'], 700, cls='fade', extra=d(.4)))
    body.append(text(860, 204, '7 / 7 passed', 14, t['teal'], 700, cls='mono fade', extra=d(.8)))
    for k in range(7):
        cx = 548 + k * 44
        cy = 232
        body.append(
            f'<g class="pop"{d(.5 + k * .08)}>'
            f'<circle cx="{cx}" cy="{cy}" r="15" fill="{t["teal"]}" fill-opacity="{t["soft"]}" stroke="{t["teal"]}" stroke-width="2"/>'
            f'<path d="M{cx - 6} {cy} l4 4 l8 -8" fill="none" stroke="{t["teal"]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
            f'</g>'
        )
    # Row B: Without SFP (0/7 rose cross circles)
    body.append(text(530, 284, 'Without SFP (no skill)', 14, t['ink2'], 500, cls='fade', extra=d(.6)))
    body.append(text(860, 284, '0 / 7 passed', 14, t['rose'], 700, cls='mono fade', extra=d(1.0)))
    for k in range(7):
        cx = 548 + k * 44
        cy = 312
        body.append(
            f'<g class="pop"{d(.7 + k * .08)}>'
            f'<circle cx="{cx}" cy="{cy}" r="15" fill="{t["rose"]}" fill-opacity="{t["soft"]}" stroke="{t["rose"]}" stroke-width="1.5"/>'
            f'<path d="M{cx - 5} {cy - 5} l10 10 M{cx + 5} {cy - 5} l-10 10" fill="none" stroke="{t["rose"]}" stroke-width="2" stroke-linecap="round"/>'
            f'</g>'
        )
    desc = (f'In blind UI design reviews, agents with SFP shipped in {sfp_r:.1f} rounds vs {base_r:.1f} with no skills. '
            f'On an unseen tool benchmark, agents with SFP passed 7 of 7 checks vs 0 of 7 without SFP.')
    return svg(1000, 374, 'Blind design reviews and unseen tool verification', desc, ''.join(body), t)


def tokens(t, res_data):
    """Animated dual-panel illustration: 200k Context Window Budget (left) + Local Selection Latency (right)."""
    meta = (res_data or {}).get('catalog_meta_tokens', 81691)
    used = (res_data or {}).get('results', {}).get('hive_rerank_auto', {}).get('suites', {}).get('bench', {}).get('avg_tokens', 3383)
    saved = round(100 - 100.0 * used / max(1, meta))

    body = [header(t, 'Context window cost and selection speed',
                   f'SFP cuts per-session skill overhead by {saved}%, leaving your 200k window free for code.')]
    # Left panel: Token budget comparison
    body.append(
        f'<g class="rise"{d(.15)}>'
        f'<rect x="40" y="106" width="450" height="246" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
        + text(60, 138, '1. Tokens Held in Context (Lower is Better)', 17, t['ink'], 700)
        + text(60, 158, 'Measured across 91 benchmark tasks in a 200k window', 12, t['ink2'])
        + '</g>'
    )
    t_rows = [
        ('Every skill always on', meta, 'rose', f'{meta:,} tok (41% of 200k)'),
        ('Only what SFP picked', used, 'teal', f'{used:,} tok ({saved}% less)'),
        ('Router idle (sfp only)', 700, 'sky', '~700 tok (0.3% of 200k)'),
    ]
    for i, (label, val, col, note) in enumerate(t_rows):
        y = 186 + i * 50
        c = t[col]
        bw = 155
        w_bar = max(8.0, bw * val / meta)
        body.append(text(60, y + 16, label, 13, t['ink'] if col == 'teal' else t['ink2'], 700 if col == 'teal' else 500, cls='fade', extra=d(.3 + .1 * i)))
        body.append(f'<rect x="200" y="{y}" width="{bw}" height="22" rx="5" fill="{t["grid"]}" fill-opacity=".5"/>')
        body.append(f'<rect class="grow" x="200" y="{y}" width="{w_bar:.1f}" height="22" rx="5" fill="{c}"{d(.5 + .15 * i)}/>')
        body.append(text(200 + bw + 10, y + 16, note, 12, t['ink'] if col == 'teal' else t['ink2'], 700 if col == 'teal' else 500, cls='mono fade', extra=d(.9 + .1 * i)))

    # Right panel: Selection speed
    body.append(
        f'<g class="rise"{d(.25)}>'
        f'<rect x="510" y="106" width="450" height="246" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
        + text(530, 138, '2. Time to Pick Skills on Your Machine', 17, t['ink'], 700)
        + text(530, 158, 'Local model judge runs only when word match is weak', 12, t['ink2'])
        + '</g>'
    )
    s_rows = [
        ('Words + project fit', 8, 'teal', '~3 to 7 ms (instant)'),
        ('+ Meaning (bge-m3)', 48, 'violet', '~200 ms (vector cosine)'),
        ('+ Model judge (p50)', 95, 'amber', '~360 ms typical'),
    ]
    for i, (label, pct_w, col, note) in enumerate(s_rows):
        y = 186 + i * 50
        c = t[col]
        bw = 155
        body.append(text(530, y + 16, label, 13, t['ink'] if col == 'teal' else t['ink2'], 700 if col == 'teal' else 500, cls='fade', extra=d(.35 + .1 * i)))
        body.append(f'<rect x="675" y="{y}" width="{bw}" height="22" rx="5" fill="{t["grid"]}" fill-opacity=".5"/>')
        body.append(f'<rect class="grow" x="675" y="{y}" width="{bw * pct_w / 100:.1f}" height="22" rx="5" fill="{c}"{d(.55 + .15 * i)}/>')
        body.append(text(675 + bw + 10, y + 16, note, 12, t['ink'] if col == 'teal' else t['ink2'], 700 if col == 'teal' else 500, cls='mono fade', extra=d(.95 + .1 * i)))

    desc = (f'Every skill always on costs {meta:,} tokens (41% of a 200k window), while SFP loads only {used:,} tokens '
            f'on average ({saved}% less), choosing in ~3-7 ms words-only or ~200 ms with local embeddings.')
    return svg(1000, 374, 'Context window cost and selection speed', desc, ''.join(body), t)


def hive_architecture(t):
    """Animated 5-column architecture diagram for the For Experts section."""
    body = [header(t, 'Inside the five-layer Hive engine',
                   'One select_skills call. Local models are optional; without them the deterministic layers still run.')]
    cols = [
        ('1. Scouts & Fit', 'sky', [
            ('Task Stems', 'tokenized prompt words'),
            ('Manifests', 'Cargo.toml, package.json'),
            ('Work Phase', 'Kalman filter on edits'),
            ('Tech Gate', 'drops mismatched stacks'),
        ]),
        ('2. Meaning', 'violet', [
            ('bge-m3 Vectors', 'local embedding cosine'),
            ('Skill Cards', 'descriptions & triggers'),
            ('Example Bank', 'paraphrased queries'),
            ('Adaptive Lead', 'leads if words < 50%'),
        ]),
        ('3. Local Judge', 'amber', [
            ('Auto Gate', 'fires only on weak words'),
            ('Top-20 Slate', 'reads closest candidates'),
            ('Selects 1 to 3', 'orders by direct utility'),
            ('Safe Guard', 'never overrides tech fit'),
        ]),
        ('4. Card Quorum', 'rose', [
            ('Quorum Rule', 'requires multi-signal vote'),
            ('Substitutes', 'deduplicates twin skills'),
            ('Role Slots', 'base, check, finish, style'),
            ('Confidence', '0.0% junk on edge tasks'),
        ]),
        ('5. Taste & Out', 'teal', [
            ('30d Half-Life', 'animation, text, code'),
            ('LinUCB Model', 'word-to-skill weights'),
            ('Bundle Attach', 'ordered workflow sets'),
            ('Markov Next', 'predicts next phase skill'),
        ]),
    ]
    cw, ch, top, gap = 172, 290, 108, 15
    for i, (title, col, items) in enumerate(cols):
        x = 40 + i * (cw + gap)
        c = t[col]
        g = [
            f'<g class="rise"{d(.18 + .12 * i)}>'
            f'<rect x="{x}" y="{top}" width="{cw}" height="{ch}" rx="12" fill="{t["tile"]}" stroke="{c}" stroke-width="1.5"/>'
            f'<path class="draw" pathLength="1" d="M{x + 12} {top + 1} H{x + cw - 12}" stroke="{c}" stroke-width="4" stroke-linecap="round" fill="none"{d(.45 + .12 * i)}/>'
            + text(x + 14, top + 30, title, 15, c, 700)
        ]
        for k, (head_s, sub_s) in enumerate(items):
            iy = top + 52 + k * 56
            g.append(
                f'<rect x="{x + 10}" y="{iy}" width="{cw - 20}" height="46" rx="7" fill="{t["bg"]}" stroke="{t["grid"]}" stroke-width="1"/>'
                + text(x + 18, iy + 19, head_s, 13, t['ink'], 700)
                + text(x + 18, iy + 36, sub_s, 11, t['ink2'])
            )
        g.append('</g>')
        body.append(''.join(g))
        if i < len(cols) - 1:
            x1, x2, my = x + cw, x + cw + gap, top + ch / 2
            p = f'M{x1} {my} H{x2 - 5}'
            body.append(f'<path class="draw" pathLength="1" d="{p}" stroke="{c}" stroke-width="2" fill="none"{d(.7 + .12 * i)}/>'
                        f'<path class="fade" d="M{x2} {my} l-7 -4 v8 z" fill="{c}"{d(1.0 + .12 * i)}/>')
            body.append(pulse(p, c, 1.5 + .25 * i, 1.8))

    # Bottom feedback loop from Layer 5 back to Layer 1
    ly = top + ch + 36
    loop = f'M874 {top + ch + 2} V{ly} H126 V{top + ch + 8}'
    body.append(f'<path class="draw" pathLength="1" d="{loop}" fill="none" stroke="{t["accent"]}" stroke-width="2" stroke-dasharray="1"{d(1.8)}/>')
    body.append(f'<path class="fade" d="M126 {top + ch + 2} l-5 8 h10 z" fill="{t["accent"]}"{d(2.4)}/>')
    body.append(f'<rect x="210" y="{ly - 13}" width="580" height="24" rx="6" fill="{t["bg"]}"/>')
    body.append(text(500, ly + 4, 'Feedback, test runs & commits update LinUCB & taste in ~/.sfp (zero task text stored)',
                     13, t['accent'], 600, 'middle', 'fade', d(2.2)))
    desc = ('Inside the five-layer Hive engine: 1. Scouts and Manifest Fit, 2. Semantic Meaning (bge-m3), '
            '3. Local Model Judge, 4. Skill Card Quorum and Dedup, 5. LinUCB Taste and Ordered Bundles.')
    return svg(1000, 462, 'Inside the five-layer Hive engine', desc, ''.join(body), t)


def library(t, catalog):
    per = Counter(s['category'] for s in catalog)
    total = len(catalog)
    known = {c for _, _, cs in FAMILIES for c in cs}
    fams = [(name, col, [c for c in cs if per.get(c)]) for name, col, cs in FAMILIES]
    extra = [c for c in per if c not in known]
    if extra:
        fams.append(('More', 'sky', extra))
    left, span, row_h = 230, 730, 54
    h = 120 + row_h * len(fams) + 30
    body = [header(t, f'{total:,} skills in {len(per)} categories',
                   'Install a few. SFP reaches every other skill on demand. Each block is one category, sized within its area.')]
    for r, (name, col, cs) in enumerate(fams):
        y = 112 + r * row_h
        fam_total = sum(per[c] for c in cs)
        body.append(text(40, y + 22, name, 15, t['ink'], 700, cls='fade', extra=d(.2 + .08 * r)))
        body.append(text(40, y + 40, f'{fam_total:,} skills', 12, t['ink2'], cls='fade', extra=d(.25 + .08 * r)))
        x = left
        for k, c in enumerate(sorted(cs, key=lambda c: -per[c])):
            w = max(6, span * per[c] / fam_total - 4)
            on = '#ffffff' if t is THEMES['light'] else t['bg']
            body.append(f'<g class="grow"{d(.4 + .08 * r + .05 * k)}><rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="44" rx="8" '
                        f'fill="{t[col]}"><title>{esc(c)}: {per[c]} skills</title></rect>')
            if w >= width(c, 12) + 18:
                body.append(text(x + 10, y + 20, c, 12, on, 700))
                body.append(text(x + 10, y + 36, str(per[c]), 12, on))
            elif w >= 30:
                body.append(text(x + w / 2, y + 27, str(per[c]), 11, on, 700, 'middle'))
            body.append('</g>')
            x += w + 4
    desc = f'{total:,} skills in {len(per)} categories, grouped into areas: ' + '; '.join(
        f'{name} {sum(per[c] for c in cs)}' for name, _, cs in fams) + '.'
    return svg(1000, h, 'The skill library', desc, ''.join(body), t)


ROLES = [
    ('Design and frontend', 'rose', ['frontend', 'design-styles'],
     ['impeccable', 'design-taste-frontend', 'accessibility-audit', 'frontend-a11y']),
    ('Marketing and content', 'amber', ['content-media'],
     ['article-writing', 'seo', 'marketing-campaign', 'content-engine']),
    ('Business and founders', 'amber', ['business-ops'],
     ['investor-materials', 'market-research', 'price-framing', 'persuasion-audit']),
    ('Backend and DevOps', 'sky', ['backend', 'devops', 'languages', 'data-apis', 'engineering'],
     ['postgres-patterns', 'api-design', 'docker-patterns', 'database-migrations']),
    ('Testing and security', 'teal', ['testing-quality', 'security'],
     ['e2e-testing', 'security-review', 'owasp-top-10-testing', 'tdd-workflow']),
    ('AI agents and MCP', 'violet', ['agents', 'agent-dev', 'ai-ml', 'ai-gateway', 'memory'],
     ['mcp-builder', 'agent-eval', 'skill-creator', 'hook-development']),
]


def glyph(kind, x, y, c):
    """A tiny line icon for each role card, 28 by 28."""
    s = f'fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
    shapes = {
        0: f'<rect x="{x}" y="{y + 3}" width="28" height="22" rx="4" {s}/><path d="M{x} {y + 10} H{x + 28}" {s}/><circle cx="{x + 5}" cy="{y + 6.5}" r="1" fill="{c}"/>',
        1: f'<path d="M{x + 2} {y + 18} V{y + 10} L{x + 18} {y + 3} V{y + 25} L{x + 2} {y + 18} Z M{x + 18} {y + 9} H{x + 26} M{x + 18} {y + 19} H{x + 26}" {s}/>',
        2: f'<path d="M{x + 2} {y + 25} H{x + 26} M{x + 5} {y + 21} V{y + 14} M{x + 12} {y + 21} V{y + 8} M{x + 19} {y + 21} V{y + 11} M{x + 26} {y + 21} V{y + 4}" {s}/>',
        3: f'<ellipse cx="{x + 14}" cy="{y + 6}" rx="11" ry="4" {s}/><path d="M{x + 3} {y + 6} V{y + 22} C{x + 3} {y + 27} {x + 25} {y + 27} {x + 25} {y + 22} V{y + 6} M{x + 3} {y + 14} C{x + 3} {y + 19} {x + 25} {y + 19} {x + 25} {y + 14}" {s}/>',
        4: f'<path d="M{x + 14} {y + 2} L{x + 25} {y + 7} V{y + 14} C{x + 25} {y + 21} {x + 20} {y + 25} {x + 14} {y + 27} C{x + 8} {y + 25} {x + 3} {y + 21} {x + 3} {y + 14} V{y + 7} Z M{x + 9} {y + 14} L{x + 13} {y + 18} L{x + 20} {y + 10}" {s}/>',
        5: f'<circle cx="{x + 14}" cy="{y + 14}" r="5" {s}/><path d="M{x + 14} {y + 2} V{y + 7} M{x + 14} {y + 21} V{y + 26} M{x + 2} {y + 14} H{x + 7} M{x + 21} {y + 14} H{x + 26} M{x + 5.5} {y + 5.5} L{x + 9} {y + 9} M{x + 19} {y + 19} L{x + 22.5} {y + 22.5} M{x + 22.5} {y + 5.5} L{x + 19} {y + 9} M{x + 9} {y + 19} L{x + 5.5} {y + 22.5}" {s}/>',
    }
    return shapes[kind]


def roles(t, catalog):
    per = Counter(s['category'] for s in catalog)
    names = {s['name'] for s in catalog}
    body = [header(t, 'Skills for every role', 'A few of the skills in each area. Install a preset, or let SFP pick across all of them.')]
    cw, ch = 295, 200
    for i, (title, col, cats, examples) in enumerate(ROLES):
        x, y = 40 + (i % 3) * (cw + 17.5), 108 + (i // 3) * (ch + 18)
        count = sum(per[c] for c in cats)
        ex = [e for e in examples if e in names][:4]
        c = t[col]
        g = [f'<g class="rise"{d(.2 + .1 * i)}><rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="14" fill="{t["tile"]}" '
             f'stroke="{t["grid"]}" stroke-width="1.5"/>',
             f'<path class="draw" pathLength="1" d="M{x + 14} {y + 1} H{x + cw - 14}" stroke="{c}" stroke-width="4" '
             f'stroke-linecap="round" fill="none"{d(.5 + .1 * i)}/>',
             glyph(i, x + 20, y + 22, c),
             text(x + 60, y + 36, title, 16, t['ink'], 700),
             text(x + 60, y + 55, f'{count:,} skills', 12, t['ink2'])]
        for k, e in enumerate(ex):
            ey = y + 80 + k * 28
            g.append(f'<rect x="{x + 20}" y="{ey}" width="{width(e, 12, True) + 20:.0f}" height="22" rx="6" '
                     f'fill="{c}" fill-opacity="{t["soft"]}"/>' + text(x + 30, ey + 15, e, 12, t['ink'], 500, cls='mono'))
        g.append('</g>')
        body.append(''.join(g))
    desc = 'Skills for every role: ' + '; '.join(
        f'{title}, {sum(per[c] for c in cats)} skills, for example {", ".join(e for e in ex if e in names)}'
        for title, _, cats, ex in ROLES) + '.'
    return svg(1000, 548, 'Skills for every role', desc, ''.join(body), t)


def install_steps(t):
    body = [header(t, 'Three steps', 'Windows, macOS and Linux. You need Node.js 18+ and Python 3.8+.')]
    steps = [('Install', 'npx sfp-hive install', 'finds your AI tools and adds a starter set'),
             ('Restart', 'your AI tool', 'so it loads the new skills'),
             ('Ask', 'Use sfp-hive for this task: ...', 'it names its skills, then follows them')]
    for i, (title, cmd, note) in enumerate(steps):
        x = 40 + i * 315
        col = t[COLORS[i]]
        body.append(f'<g class="rise"{d(.2 + .2 * i)}><rect x="{x}" y="110" width="290" height="140" rx="14" fill="{t["tile"]}" '
                    f'stroke="{col}" stroke-width="2"/><circle cx="{x + 34}" cy="144" r="16" fill="{col}"/>'
                    + text(x + 34, 150, str(i + 1), 16, t['on_accent'] if t is THEMES['light'] else t['bg'], 800, 'middle')
                    + text(x + 62, 150, title, 18, t['ink'], 700)
                    + f'<rect x="{x + 18}" y="172" width="254" height="30" rx="7" fill="{t["term"]}"/>'
                    + text(x + 30, 192, cmd if i != 1 else 'close and reopen it', 13, '#e6edf3', 500, cls='mono')
                    + text(x + 20, 230, note, 13, t['ink2']) + '</g>')
        if i < 2:
            body.append(f'<path class="draw" pathLength="1" d="M{x + 292} 180 H{x + 313}" stroke="{t["accent"]}" '
                        f'stroke-width="2"{d(.6 + .2 * i)}/>')
    for i, os_name in enumerate(['Windows', 'macOS', 'Linux']):
        x = 40 + i * 118
        body.append(f'<g class="pop"{d(1.0 + .1 * i)}><rect x="{x}" y="270" width="108" height="30" rx="15" '
                    f'fill="none" stroke="{t["grid"]}" stroke-width="1.5"/>' + text(x + 54, 290, os_name, 13, t['ink'], 600, 'middle') + '</g>')
    body.append(text(400, 290, 'Claude Code users can add the plugin instead: /plugin marketplace add siddu1004/SFP',
                     13, t['ink2'], cls='fade', extra=d(1.3)))
    desc = ('Install SFP in three steps on Windows, macOS or Linux: run npx sfp-hive install, restart your AI tool, '
            'then ask it to use sfp-hive for a task.')
    return svg(1000, 320, 'Install SFP in three steps', desc, ''.join(body), t)


def terminal(t, example):
    task = example['task']
    stack = [s['name'] for s in example.get('stack', [])]
    bundles = [b['name'] for b in (example.get('bundles_applied') or [])]
    used = example.get('tokens_used') or 0
    share = example.get('share_of_200k') or 0
    cmd = f'sfp select "{task}"'
    lines = [('ink', f'{i + 1}. {n}') for i, n in enumerate(stack)]
    if bundles:
        lines.append(('accent', 'Bundle: ' + ', '.join(bundles)))
    lines.append(('ink2', f'{used:,} tokens, {share}% of a 200k window'))
    h = 150 + 26 * len(lines)
    size = 14
    body = [f'<rect x="20" y="20" width="960" height="{h - 40}" rx="12" fill="{t["term"]}"/>']
    for i, c in enumerate(['#ff5f57', '#febc2e', '#28c840']):
        body.append(f'<circle cx="{46 + i * 20}" cy="44" r="6" fill="{c}"/>')
    body.append(text(500, 49, 'sfp: words only, no model', 12, '#9aa4b0', anchor='middle'))
    body.append(text(44, 92, '$', size, '#2dd4bf', 700, cls='mono'))
    body.append(text(62, 92, cmd, size, '#e6edf3', cls='mono'))
    cmd_w = width(cmd, size, True)
    steps = len(cmd)
    body.append(f'<rect class="cover" x="60" y="74" width="{cmd_w + 20:.0f}" height="26" fill="{t["term"]}">'
                f'<animate attributeName="x" from="60" to="{62 + cmd_w:.0f}" dur="{steps * .035:.2f}s" begin=".3s" '
                f'fill="freeze" calcMode="discrete" values="{";".join(f"{60 + k * cmd_w / steps:.1f}" for k in range(steps + 1))}"/></rect>')
    start = .3 + steps * .035 + .2
    palette = {'ink': '#e6edf3', 'ink2': '#9aa4b0', 'accent': '#2dd4bf'}
    for i, (col, line) in enumerate(lines):
        body.append(text(62, 130 + 26 * i, line, size, palette[col], 700 if col == 'accent' else 400, cls='mono fade',
                         extra=d(start + .18 * i)))
    y_end = 130 + 26 * len(lines)
    body.append(text(44, y_end, '$', size, '#2dd4bf', 700, cls='mono fade', extra=d(start + .18 * len(lines))))
    body.append(f'<rect class="blink" x="62" y="{y_end - 13}" width="9" height="16" fill="#e6edf3"/>')
    desc = f'A terminal running {cmd}. SFP answers with {", ".join(stack)}' + (
        f' and the bundle {", ".join(bundles)}' if bundles else '') + f', {used:,} tokens in all.'
    return svg(1000, h, 'Ask SFP from the terminal', desc, ''.join(body), t)


def ui_flow(t):
    """Dedicated animated workflow for UI, Design Systems, Accessibility & Motion."""
    body = [header(t, 'UI, design systems and motion workflows',
                   'Ordered frontend bundles guide your AI from semantic markup and typography scale to hardware-accelerated motion.')]
    tracks = [
        ('Accessible UI & Forms Bundle', 'rose', 150, [
            ('frontend-a11y', 'semantic HTML & ARIA'),
            ('ux-writing', 'concise microcopy'),
            ('react-patterns', 'state & composition'),
            ('accessibility-audit', 'WCAG & keyboard check'),
        ]),
        ('Visual Taste & Motion Studio', 'violet', 265, [
            ('design-taste-frontend', 'hierarchy & spacing'),
            ('impeccable', 'editorial polish'),
            ('animate', 'spring & CSS motion'),
            ('break-ui', 'layout stress test'),
        ]),
    ]
    for tr, (label, col, y, nodes) in enumerate(tracks):
        c = t[col]
        body.append(text(40, y - 34, label, 13, c, 700, cls='fade', extra=d(.15 + .2 * tr)))
        w = 212
        for i, (name, sub) in enumerate(nodes):
            x = 40 + i * 242
            disp = name if len(name) <= 19 else name[:18] + '..'
            body.append(f'<g class="rise"{d(.2 + .12 * i + .2 * tr)}><rect x="{x}" y="{y - 24}" width="{w}" height="58" '
                        f'rx="12" fill="{t["tile"]}" stroke="{c}" stroke-width="2"/>'
                        f'<circle cx="{x + 22}" cy="{y + 5}" r="11" fill="{c}"/>'
                        + text(x + 22, y + 9, str(i + 1), 11, '#ffffff' if t is THEMES['light'] else t['bg'], 700, 'middle')
                        + text(x + 40, y, disp, 12, t['ink'], 700, cls='mono')
                        + text(x + 40, y + 18, sub, 12, t['ink2']) + '</g>')
            if i < len(nodes) - 1:
                x1, x2 = x + w, x + 242
                p = f'M{x1} {y + 5} H{x2 - 6}'
                body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="2"{d(.6 + .15 * i + .2 * tr)}/>'
                            f'<path class="fade" d="M{x2} {y + 5} l-8 -4 v8 z" fill="{c}"{d(1.1 + .15 * i + .2 * tr)}/>')
                body.append(pulse(p, c, 1.8 + .35 * i + .4 * tr, 1.8))
    desc = ('Two ordered UI and frontend bundles: Accessible UI & Forms Bundle (frontend-a11y -> ux-writing -> react-patterns -> '
            'accessibility-audit) and Visual Taste & Motion Studio (design-taste-frontend -> impeccable -> animate -> break-ui).')
    return svg(1000, 355, 'UI, design systems and motion workflows', desc, ''.join(body), t)


def growth_flow(t):
    """Dedicated animated workflow for Business, Marketing, Fundraising & Content."""
    body = [header(t, 'Business, fundraising and content growth engines',
                   'From market sizing and pricing psychology to operator-voice articles, technical SEO and multi-channel distribution.')]
    tracks = [
        ('Fundraise & Positioning Pipeline', 'amber', 150, [
            ('market-research', 'TAM & positioning'),
            ('price-framing', 'tiers & packaging'),
            ('investor-materials', 'deck & narrative'),
            ('investor-outreach', 'warm & cold outreach'),
        ]),
        ('Publish & Growth Content Engine', 'teal', 265, [
            ('brand-voice', 'operator voice profile'),
            ('article-writing', 'proof-led long-form'),
            ('seo', 'intent & schema audit'),
            ('content-engine', 'multi-channel launch'),
        ]),
    ]
    for tr, (label, col, y, nodes) in enumerate(tracks):
        c = t[col]
        body.append(text(40, y - 34, label, 13, c, 700, cls='fade', extra=d(.15 + .2 * tr)))
        w = 212
        for i, (name, sub) in enumerate(nodes):
            x = 40 + i * 242
            disp = name if len(name) <= 19 else name[:18] + '..'
            body.append(f'<g class="rise"{d(.2 + .12 * i + .2 * tr)}><rect x="{x}" y="{y - 24}" width="{w}" height="58" '
                        f'rx="12" fill="{t["tile"]}" stroke="{c}" stroke-width="2"/>'
                        f'<circle cx="{x + 22}" cy="{y + 5}" r="11" fill="{c}"/>'
                        + text(x + 22, y + 9, str(i + 1), 11, '#ffffff' if t is THEMES['light'] else t['bg'], 700, 'middle')
                        + text(x + 40, y, disp, 12, t['ink'], 700, cls='mono')
                        + text(x + 40, y + 18, sub, 12, t['ink2']) + '</g>')
            if i < len(nodes) - 1:
                x1, x2 = x + w, x + 242
                p = f'M{x1} {y + 5} H{x2 - 6}'
                body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="2"{d(.6 + .15 * i + .2 * tr)}/>'
                            f'<path class="fade" d="M{x2} {y + 5} l-8 -4 v8 z" fill="{c}"{d(1.1 + .15 * i + .2 * tr)}/>')
                body.append(pulse(p, c, 1.8 + .35 * i + .4 * tr, 1.8))
    desc = ('Two ordered business and marketing bundles: Fundraise & Positioning Pipeline (market-research -> price-framing -> '
            'investor-materials -> investor-outreach) and Publish & Growth Content Engine (brand-voice -> article-writing -> seo -> content-engine).')
    return svg(1000, 355, 'Business, fundraising and content growth workflows', desc, ''.join(body), t)


def tools(t):
    body = [header(t, 'Works where you already work', 'Skills install into each tool’s own folder. Anything that speaks MCP can use all of them.')]
    x, y = 40, 112
    for i, name in enumerate(TOOLS):
        w = width(name, 14) + 40
        if x + w > 960:
            x, y = 40, y + 48
        col = t[COLORS[i % len(COLORS)]]
        last = name == 'Any MCP client'
        body.append(f'<g class="pop"{d(.2 + .04 * i)}><rect x="{x}" y="{y}" width="{w:.0f}" height="36" rx="18" '
                    f'fill="{t["accent"] if last else t["tile"]}" stroke="{col}" stroke-width="1.5"/>'
                    f'<circle cx="{x + 18}" cy="{y + 18}" r="4" fill="{t["on_accent"] if last else col}"/>'
                    + text(x + 30, y + 23, name, 14, t['on_accent'] if last else t['ink'], 600) + '</g>')
        x += w + 10
    h = y + 70
    return svg(1000, h, 'Supported AI tools', 'SFP works with ' + ', '.join(TOOLS) + '.', ''.join(body), t)


# ----------------------------------------------------------------- main


def write(name, theme, body):
    os.makedirs(ASSETS, exist_ok=True)
    with open(os.path.join(ASSETS, f'{name}-{theme}.svg'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)


def main():
    catalog = load_catalog()
    total, ncats = len(catalog), len({s['category'] for s in catalog})
    hero_example = hive('make the login not get hacked') or {'task': 'make the login not get hacked', 'stack': []}
    hero_example.setdefault('task', 'make the login not get hacked')
    term_example = hive('build a signup page with a form, store users in postgres, '
                        'add end to end tests and deploy it with docker')
    term_example.setdefault('task', 'build a signup page')
    scores = exam_scores()
    res_data = latest_results()
    dz = design_numbers()
    for name, t in THEMES.items():
        hero_svg = hero(t, total, ncats, hero_example)
        write('banner', name, hero_svg)
        write('hero', name, hero_svg)
        write('pipeline', name, pipeline(t))
        write('advantages', name, advantages(t, total))
        write('project-fit', name, project_fit(t))
        write('taste', name, taste(t))
        write('plain-words', name, plain_words(t))
        write('library', name, library(t, catalog))
        write('roles', name, roles(t, catalog))
        write('install-steps', name, install_steps(t))
        write('terminal', name, terminal(t, term_example))
        write('ui-flow', name, ui_flow(t))
        write('growth-flow', name, growth_flow(t))
        write('results-rounds', name, results_rounds(t, dz))
        write('tokens', name, tokens(t, res_data))
        write('hive-architecture', name, hive_architecture(t))
        write('tools', name, tools(t))
        if scores:
            write('exam', name, exam(t, scores))
    print('README art written to assets/: banner, hero, pipeline, advantages, project-fit, taste, plain-words, '
          'library, roles, install-steps, terminal, ui-flow, growth-flow, results-rounds, tokens, hive-architecture, tools'
          + (', exam' if scores else ''))


if __name__ == '__main__':
    main()
