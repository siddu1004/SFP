"""Draw the README's animated illustrations, in the same dark and light themes as bench/charts.py.

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
    task = example['task']
    stack = [s['name'] for s in example.get('stack', [])][:3] or ['security-review']
    body = [f'<defs><radialGradient id="g" cx="78%" cy="45%" r="55%"><stop offset="0" stop-color="{t["accent"]}" '
            f'stop-opacity="{t["soft"]}"/><stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/>'
            f'</radialGradient></defs><rect width="1280" height="400" rx="16" fill="url(#g)"/>']
    body.append(text(56, 92, 'SKILLS FOR PRODUCTIVITY', 14, t['accent'], 700, cls='rise',
                     extra=' letter-spacing="3"'))
    body.append(text(52, 190, 'SFP', 112, t['ink'], 800, cls='rise', extra=d(.08) + ' letter-spacing="-4"'))
    body.append(text(56, 240, 'The right skills for every task,', 28, t['ink'], 600, cls='rise', extra=d(.18)))
    body.append(text(56, 276, 'picked on your machine.', 28, t['ink'], 600, cls='rise', extra=d(.24)))
    facts = [f'{total:,} skills', f'{ncats} categories', '20 AI tools', 'free, MIT']
    x = 56
    for i, f in enumerate(facts):
        wv = width(f, 14) + 28
        body.append(f'<g class="rise"{d(.4 + i * .08)}><rect x="{x}" y="310" width="{wv:.0f}" height="32" rx="16" '
                    f'fill="{t["tile"]}" stroke="{t[COLORS[i]]}" stroke-width="1.5"/>'
                    + text(x + wv / 2, 331, f, 14, t['ink'], 600, 'middle') + '</g>')
        x += wv + 10

    # The shelf: one tile per group of skills, coloured by family.
    gx, gy, cols, rows, size, gap = 620, 84, 10, 8, 28, 8
    lit = [(1, 6), (4, 2), (6, 7)][:len(stack)]
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            x0, y0 = gx + c * (size + gap), gy + r * (size + gap)
            color = t[COLORS[(c * 7 + r * 3) % len(COLORS)]]
            body.append(f'<rect class="pop" x="{x0}" y="{y0}" width="{size}" height="{size}" rx="6" fill="{color}" '
                        f'fill-opacity="{t["soft"]}"{d(.2 + i * .006)}/>')
    # The task, the lines to the chosen tiles, and the stack.
    cw = width(task, 14) + 34
    body.append(f'<g class="rise"{d(.5)}><rect x="{gx}" y="30" width="{cw:.0f}" height="34" rx="17" fill="{t["tile"]}" '
                f'stroke="{t["grid"]}" stroke-width="1.5"/>' + text(gx + 17, 52, f'“{task}”', 14, t['ink']) + '</g>')
    card_x, card_y = 1018, 132
    body.append(f'<g class="rise"{d(1.6)}><rect x="{card_x}" y="{card_y}" width="232" height="{60 + 40 * len(stack)}" '
                f'rx="12" fill="{t["tile"]}" stroke="{t["accent"]}" stroke-width="2"/>'
                + text(card_x + 18, card_y + 32, 'Your stack', 15, t['ink'], 700) + '</g>')
    for i, (r, c) in enumerate(lit):
        cx, cy = gx + c * (size + gap) + size / 2, gy + r * (size + gap) + size / 2
        ry = card_y + 62 + 40 * i
        p1 = f'M{gx + 40} 64 C{gx + 40} {cy - 40} {cx - 60} {cy} {cx - size / 2} {cy}'
        p2 = f'M{cx + size / 2} {cy} C{cx + 90} {cy} {card_x - 70} {ry} {card_x} {ry}'
        for k, p in enumerate((p1, p2)):
            body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{t["accent"]}" '
                        f'stroke-width="2" stroke-linecap="round"{d(.8 + .5 * k + .15 * i)}/>')
        body.append(f'<rect class="glow" x="{cx - size / 2 - 3}" y="{cy - size / 2 - 3}" width="{size + 6}" '
                    f'height="{size + 6}" rx="8" fill="{t["accent"]}"/>')
        body.append(pulse(p2, t['accent'], 2.2 + .4 * i))
        body.append(f'<g class="rise"{d(1.8 + .15 * i)}><circle cx="{card_x + 28}" cy="{ry - 5}" r="11" fill="{t["accent"]}"/>'
                    + text(card_x + 28, ry, str(i + 1), 12, t['on_accent'], 700, 'middle')
                    + text(card_x + 46, ry, stack[i], 12, t['ink'], 500, cls='mono') + '</g>')
    desc = (f'SFP keeps {total:,} skills on a shelf. For the task "{task}" it lights up the few that fit and hands '
            f'them to your AI: {", ".join(stack)}.')
    return svg(1280, 400, 'SFP: Skills for Productivity', desc, ''.join(body), t)


def pipeline(t):
    body = [header(t, 'How SFP picks', 'Everything runs on your machine. Dashed steps are optional and need a local model.')]
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
    body.append(text(735, 387, 'learns from “helped” and “did not help”', 13, t['accent'], 600, 'middle', 'fade', d(3.0)))
    desc = ('Your task and project go to three signals: words, meaning and project fit. Rank fusion joins them into '
            'one shortlist, an optional local model orders it, and you get one to three skills plus fitting bundles. '
            'Your feedback flows back into the choice.')
    return svg(1000, 410, 'How SFP picks', desc, ''.join(body), t)


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


def library(t, catalog):
    per = Counter(s['category'] for s in catalog)
    total = len(catalog)
    known = {c for _, _, cs in FAMILIES for c in cs}
    fams = [(name, col, [c for c in cs if per.get(c)]) for name, col, cs in FAMILIES]
    extra = [c for c in per if c not in known]
    if extra:
        fams.append(('More', 'sky', extra))
    biggest = max(sum(per[c] for c in cs) for _, _, cs in fams)
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
            on = '#ffffff' if t is THEMES['light'] else t['bg']  # dark ink on bright tiles, white on deep ones
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
             ('Ask', 'Use sfp-hive for this task: …', 'it names its skills, then follows them')]
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
    body = [header(t, 'UI, design and growth workflows',
                   'Ordered skill bundles guide your AI from layout and microcopy to accessible code and launch copy.')]
    tracks = [
        ('Accessible UI Bundle', 'rose', 150, [
            ('frontend-a11y', 'semantic HTML & ARIA'),
            ('ux-writing', 'concise microcopy'),
            ('react-patterns', 'state & composition'),
            ('accessibility-audit', 'WCAG & keyboard check'),
        ]),
        ('Growth & Launch Bundle', 'amber', 265, [
            ('market-research', 'audience & positioning'),
            ('price-framing', 'packaging & tiers'),
            ('article-writing', 'launch narrative'),
            ('seo', 'search & distribution'),
        ]),
    ]
    for tr, (label, col, y, nodes) in enumerate(tracks):
        c = t[col]
        body.append(text(40, y - 34, label, 13, c, 700, cls='fade', extra=d(.15 + .2 * tr)))
        w = 212
        for i, (name, sub) in enumerate(nodes):
            x = 40 + i * 242
            body.append(f'<g class="rise"{d(.2 + .12 * i + .2 * tr)}><rect x="{x}" y="{y - 24}" width="{w}" height="58" '
                        f'rx="12" fill="{t["tile"]}" stroke="{c}" stroke-width="2"/>'
                        f'<circle cx="{x + 22}" cy="{y + 5}" r="11" fill="{c}"/>'
                        + text(x + 22, y + 9, str(i + 1), 11, '#ffffff' if t is THEMES['light'] else t['bg'], 700, 'middle')
                        + text(x + 42, y, name, 13, t['ink'], 700, cls='mono')
                        + text(x + 42, y + 18, sub, 12, t['ink2']) + '</g>')
            if i < len(nodes) - 1:
                x1, x2 = x + w, x + 242
                p = f'M{x1} {y + 5} H{x2 - 6}'
                body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="2"{d(.6 + .15 * i + .2 * tr)}/>'
                            f'<path class="fade" d="M{x2} {y + 5} l-8 -4 v8 z" fill="{c}"{d(1.1 + .15 * i + .2 * tr)}/>')
                body.append(pulse(p, c, 1.8 + .35 * i + .4 * tr, 1.8))
    desc = ('Two ordered skill bundles: Accessible UI Bundle (frontend-a11y -> ux-writing -> react-patterns -> '
            'accessibility-audit) and Growth & Launch Bundle (market-research -> price-framing -> article-writing -> seo).')
    return svg(1000, 355, 'UI, design and growth workflows', desc, ''.join(body), t)


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
    for name, t in THEMES.items():
        write('hero', name, hero(t, total, ncats, hero_example))
        write('pipeline', name, pipeline(t))
        write('library', name, library(t, catalog))
        write('roles', name, roles(t, catalog))
        write('install-steps', name, install_steps(t))
        write('terminal', name, terminal(t, term_example))
        write('ui-flow', name, ui_flow(t))
        write('tools', name, tools(t))
        if scores:
            write('exam', name, exam(t, scores))
    print('README art written to assets/: hero, pipeline, library, roles, install-steps, terminal, ui-flow, tools'
          + (', exam' if scores else ''))


if __name__ == '__main__':
    main()
