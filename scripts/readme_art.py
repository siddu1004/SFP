"""Draw the README's animated illustrations, in dark and light themes.

Every number and example comes from the repository itself: the catalog,
bench/results/release.json, and real words-only output from the hive. Run it after a benchmark,
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
from collections import Counter

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


# ----------------------------------------------------------------- measured results


def release():
    """bench/results/release.json (bench/release.py): the one source of every accuracy, speed and token figure drawn here."""
    try:
        with open(os.path.join(ROOT, 'bench', 'results', 'release.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def got(rel, engine, *path):
    x = rel.get('engines', {}).get(engine, {})
    for p in path:
        x = x.get(p) if isinstance(x, dict) else None
    return x


def engines_shown(rel):
    rows = [('keyword', 'Keyword search', 'muted'), ('words', 'SFP, no model', 'sky'), ('meaning', 'SFP + bge-m3', 'teal')]
    return [r for r in rows if r[0] in rel.get('engines', {})]


def best_engine(rel):
    return 'meaning' if 'meaning' in rel.get('engines', {}) else 'words'


def all_on_tokens(catalog):
    return sum(-(-(len(s['name']) + len(s['description']) + 12) // 4) for s in catalog)


def context_saved(rel, catalog):
    used = (got(rel, best_engine(rel), 'tokens', 'stack') or 0) + (got(rel, best_engine(rel), 'tokens', 'map') or 0)
    return used, round(100 - 100.0 * used / all_on_tokens(catalog)) if used else 0


SAME = r"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.getcwd(), 'mcp'))
import sfp_hive as eng
hist, out = eng.History(eng.v1.RECIPES, []), []
with tempfile.TemporaryDirectory() as tmp:
    homes = {}
    for f in ('stack_eval.json', 'hive_heldout.json'):
        data = json.load(open(os.path.join('tests', f), encoding='utf-8'))
        eng._projects(data, os.path.join(tmp, f))
        homes.update({k: os.path.join(tmp, f, k) for k in data['projects']})
    for label, key in (('Next.js', 'nextjs'), ('Rust', 'rust'), ('.NET', 'dotnet'), ('Flutter', 'flutter'), ('Django', 'django')):
        out.append([label, [c['name'] for c in eng.select('write tests for the orders', homes[key], history=hist)['stack']]])
print(json.dumps(out))
"""
STORY = r"""
import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), 'mcp'))
import sfp_city
print(json.dumps(sfp_city.story(sys.argv[1])))
"""


def ask_python(code, *args):
    """Run a little code against the engine, words only, in a throwaway data folder."""
    env = dict(os.environ, SFP_SEMANTIC='0', SFP_DATA_DIR=tempfile.mkdtemp(prefix='sfp-art-'), PYTHONIOENCODING='utf-8')
    done = subprocess.run([sys.executable, '-c', code] + list(args), capture_output=True, text=True, encoding='utf-8', env=env, cwd=ROOT, timeout=180)
    try:
        return json.loads(done.stdout)
    except ValueError:
        return None


# ----------------------------------------------------------------- the city


def block(cx, cy, w, depth, height, color, t, lit=False, floors=0, cls='', delay=0.0):
    """One isometric building standing on (cx, cy), the middle of its ground tile."""
    hw, hd = w / 2, depth / 2
    top = cy - height
    left = f'{cx - hw},{cy} {cx},{cy + hd} {cx},{top + hd} {cx - hw},{top}'
    right = f'{cx + hw},{cy} {cx},{cy + hd} {cx},{top + hd} {cx + hw},{top}'
    roof = f'{cx - hw},{top} {cx},{top + hd} {cx + hw},{top} {cx},{top - hd}'
    a, b, c = (1.0, .78, .55) if lit else (.5, .34, .22)
    s = f'<g class="{cls}"{d(delay)}>' if cls else '<g>'
    for pts, o in ((left, b), (right, c), (roof, a)):
        s += f'<polygon points="{pts}" fill="{t["bg"]}"/><polygon points="{pts}" fill="{color}" fill-opacity="{o}"/>'
    for k in range(1, floors):
        y = cy - height * k / floors
        s += (f'<path d="M{cx - hw} {y:.1f} L{cx} {y + hd:.1f} L{cx + hw} {y:.1f}" fill="none" stroke="{t["bg"]}" '
              f'stroke-width="1.5" stroke-opacity=".8"/>')
    return s + '</g>'


def city_blocks(t, catalog, x0, y0, tw, td, cols, tallest, lit=(), delay=.2):
    """Every category is a building; its height grows with its skills. Returns (svg, {category: roof point})."""
    per = Counter(s['category'] for s in catalog)
    color = {c: col for _, col, cs in FAMILIES for c in cs}
    cats = sorted(per, key=lambda c: (next((i for i, f in enumerate(FAMILIES) if c in f[2]), 9), -per[c]))
    top = max(per.values()) ** .5
    spots, out, roofs = [], [], {}
    for k, c in enumerate(cats):
        i, j = k % cols, k // cols
        spots.append((i + j, x0 + (i - j) * tw / 2, y0 + (i + j) * td / 2, c))
    for n, (_, x, y, c) in enumerate(sorted(spots)):
        h = 8 + tallest * (per[c] ** .5) / top
        out.append(block(x, y, tw * .78, td * .78, h, t[color.get(c, 'sky')], t, c in lit, cls='rise', delay=delay + .025 * n))
        roofs[c] = (x, y - h)
    return ''.join(out), roofs


def hero(t, total, ncats, example, catalog, rel):
    """The banner: the skill city, the task, and the towers it lights up."""
    task = example['task']
    chosen = example.get('stack', [])[:3]
    stack = [s['name'] for s in chosen]
    lit = [s['category'] for s in chosen]
    used, saved = context_saved(rel, catalog)
    hold = got(rel, best_engine(rel), 'map', 'hold', '40')
    body = [f'<defs><radialGradient id="g" cx="66%" cy="56%" r="46%"><stop offset="0" stop-color="{t["accent"]}" '
            f'stop-opacity="{t["soft"]}"/><stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/>'
            f'</radialGradient></defs><rect width="1280" height="360" rx="16" fill="url(#g)"/>']
    body.append(text(56, 76, 'SKILLS FOR PRODUCTIVITY', 13, t['accent'], 700, cls='rise', extra=' letter-spacing="3"'))
    body.append(text(52, 172, 'SFP', 108, t['ink'], 800, cls='rise', extra=d(.08) + ' letter-spacing="-4"'))
    body.append(text(56, 218, f'A city of {total:,} skills for your AI.', 26, t['ink'], 700, cls='rise', extra=d(.16)))
    body.append(text(56, 248, 'It reads your task and lights up the few that fit.', 17, t['ink2'], 500, cls='rise', extra=d(.22)))
    for i, (label, col) in enumerate([('AI and MCP', 'violet'), ('UI and design', 'rose'), ('Engineering', 'sky'),
                                      ('Business and content', 'amber'), ('Testing and security', 'teal'), ('Science and docs', 'lime')]):
        px, py, c = 56 + (i % 3) * 172, 274 + (i // 3) * 34, t[col]
        body.append(f'<g class="rise"{d(.32 + i * .06)}><rect x="{px}" y="{py}" width="162" height="26" rx="13" '
                    f'fill="{t["tile"]}" stroke="{c}" stroke-width="1.5"/><circle cx="{px + 15}" cy="{py + 13}" r="4" fill="{c}"/>'
                    + text(px + 26, py + 17, label, 12, t['ink'], 600) + '</g>')
    drawn, roofs = city_blocks(t, catalog, 780, 148, 68, 34, 6, 92, lit)
    body.append(drawn)
    cw = width(f'Task: "{task}"', 13) + 36
    body.append(f'<g class="rise"{d(.45)}><rect x="620" y="22" width="{cw:.0f}" height="34" rx="17" fill="{t["tile"]}" '
                f'stroke="{t["grid"]}" stroke-width="1.5"/>' + text(638, 44, f'Task: "{task}"', 13, t['ink'], 600) + '</g>')
    card_x, card_y = 1012, 104
    body.append(f'<g class="rise"{d(1.2)}><rect x="{card_x}" y="{card_y}" width="242" height="{86 + 34 * len(stack)}" '
                f'rx="12" fill="{t["tile"]}" stroke="{t["accent"]}" stroke-width="2"/>'
                + text(card_x + 18, card_y + 30, 'Picked for this task', 14, t['ink'], 700) + '</g>')
    for i, n in enumerate(stack):
        ry = card_y + 60 + 34 * i
        rx, rtop = roofs.get(lit[i], (780, 200))
        p = f'M{rx} {rtop} C{rx + 60} {rtop - 34} {card_x - 70} {ry - 4} {card_x} {ry - 4}'
        body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{t["accent"]}" stroke-width="2" '
                    f'stroke-linecap="round"{d(.8 + .2 * i)}/><circle class="glow" cx="{rx}" cy="{rtop}" r="5" fill="{t["accent"]}"/>')
        body.append(pulse(p, t['accent'], 2.0 + .4 * i))
        body.append(f'<g class="rise"{d(1.4 + .15 * i)}><circle cx="{card_x + 26}" cy="{ry - 4}" r="10" fill="{t["accent"]}"/>'
                    + text(card_x + 26, ry, str(i + 1), 11, t['on_accent'], 700, 'middle')
                    + text(card_x + 42, ry, n if len(n) <= 25 else n[:23] + '..', 12, t['ink'], 600, cls='mono') + '</g>')
    note = 'and a map of the next 40' if hold else 'only what fits'
    body.append(text(card_x + 18, card_y + 70 + 34 * len(stack), note, 12, t['accent'], 600, cls='fade', extra=d(1.9)))
    desc = (f'SFP is a city of {total:,} skills in {ncats} categories. For the task "{task}" it lights up the few buildings that '
            f'fit and hands them to your AI: {", ".join(stack)}.')
    return svg(1280, 360, 'SFP: Skills for Productivity', desc, ''.join(body), t)


def skyline(t, x, y, heights, color, w=11, gap=4, delay=0.0, tall=34):
    out = ''
    for k, h in enumerate(heights):
        out += (f'<rect class="rise" x="{x + k * (w + gap)}" y="{y - tall * h:.1f}" width="{w}" height="{tall * h:.1f}" rx="2" '
                f'fill="{color}"{d(delay + .04 * k)}/>')
    return out


def pipeline(t):
    body = [header(t, 'How SFP picks', 'Each reader draws a map of the city. The tallest buildings over all the maps win. Dashed needs a local model.')]
    readers = [('Words', 'sky', False, [.3, .8, .2, .5, .1]), ('Full text', 'lime', False, [.5, .9, .3, .2, .2]),
               ('Requests', 'amber', False, [.2, .7, .4, .6, .1]), ('Meaning', 'violet', True, [.4, 1., .3, .3, .2]),
               ('Your project', 'rose', False, [.6, .8, 0.06, .5, 0.06])]
    body.append(f'<g class="rise"{d(.15)}><rect x="40" y="214" width="140" height="74" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" '
                f'stroke-width="2"/>' + text(58, 246, 'Your task', 16, t['ink'], 700) + text(58, 268, 'in your words', 13, t['ink2']) + '</g>')
    for i, (name, col, dashed, hs) in enumerate(readers):
        y, c = 106 + i * 60, t[col]
        dash = ' stroke-dasharray="6 5"' if dashed else ''
        body.append(f'<g class="rise"{d(.25 + .1 * i)}><rect x="250" y="{y}" width="236" height="50" rx="10" fill="{t["tile"]}" '
                    f'stroke="{c}" stroke-width="2"{dash}/>' + text(266, y + 31, name, 15, t['ink'], 700) + '</g>')
        body.append(skyline(t, 394, y + 43, hs, c, delay=.5 + .1 * i))
        a, b = f'M180 251 C215 251 215 {y + 25} 244 {y + 25}', f'M486 {y + 25} C530 {y + 25} 530 251 574 251'
        for k, p in enumerate((a, b)):
            body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="1.8"{d(.5 + .5 * k + .08 * i)}/>')
        body.append(pulse(b, c, 2.0 + .3 * i, 2.0))
    body.append(f'<g class="rise"{d(1.0)}><rect x="580" y="176" width="180" height="150" rx="14" fill="{t["tile"]}" stroke="{t["accent"]}" '
                f'stroke-width="2.5"/>' + text(670, 204, 'City selector', 16, t['ink'], 700, 'middle') + '</g>')
    for k, (h, on) in enumerate([(26, 0), (74, 1), (34, 0), (46, 0)]):
        body.append(block(616 + k * 36, 296, 30, 15, h, t['accent'] if on else t['muted'], t, bool(on), floors=max(2, h // 14), cls='rise', delay=1.1 + .1 * k))
    outs = [('1 to 3 skills', 'loaded for this job', 'teal', 128), ('Map of the next 40', 'your AI can swap one in', 'violet', 214),
            ('Or nothing', 'when no skill fits', 'ink2', 300)]
    for i, (a, b, col, y) in enumerate(outs):
        c = t[col]
        p = f'M760 251 C795 251 795 {y + 33} 818 {y + 33}'
        body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="2"{d(1.4 + .12 * i)}/>'
                    f'<path class="fade" d="M826 {y + 33} l-9 -5 v10 z" fill="{c}"{d(2.0)}/>')
        body.append(f'<g class="rise"{d(1.5 + .12 * i)}><rect x="828" y="{y}" width="142" height="66" rx="12" fill="{t["tile"]}" stroke="{c}" '
                    f'stroke-width="2"/>' + text(840, y + 28, a, 13, t['ink'], 700) + text(840, y + 48, b, 11, t['ink2']) + '</g>')
    loop = 'M899 372 V424 H670 V332'
    body.append(f'<path class="draw" pathLength="1" d="{loop}" fill="none" stroke="{t["accent"]}" stroke-width="2"{d(2.2)}/>'
                f'<path class="fade" d="M670 328 l-5 9 h10 z" fill="{t["accent"]}"{d(2.8)}/>')
    body.append(text(656, 429, 'what helped moves the weights', 13, t['accent'], 600, 'end', 'fade', d(2.6)))
    desc = ('Your task goes to five readers: words, full text, requests, meaning and your project. Each draws a map of heights over '
            'the skills. A learned selector adds the maps and returns one to three skills, a map of the next forty your AI can choose '
            'from, or nothing when no skill fits. Your feedback moves its weights.')
    return svg(1000, 446, 'How SFP picks', desc, ''.join(body), t)


def city(t, story, example):
    """One building's story, and the towers a real task raises."""
    body = [header(t, 'The skill city', 'Every skill is a building with a story. A task raises towers; the tallest are read first.')]
    c = t['accent']
    body.append(f'<g class="rise"{d(.15)}><rect x="40" y="106" width="350" height="316" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" '
                f'stroke-width="1.5"/>' + text(60, 138, 'One building', 13, c, 700) + text(60, 164, story['name'], 18, t['ink'], 700, cls='mono') + '</g>')
    words = story['does'].split()
    lines, line = [], ''
    for w in words:
        if len(line) + len(w) > 46:
            lines.append(line)
            line = ''
        line = (line + ' ' + w).strip()
    lines = (lines + [line])[:2]
    if len(' '.join(lines)) < len(story['does']):
        lines[-1] = lines[-1].rstrip(' ,.;') + '...'
    for k, ln in enumerate(lines):
        body.append(text(60, 190 + 18 * k, ln, 12, t['ink2'], cls='fade', extra=d(.3)))
    body.append(text(60, 246, 'Words that call it', 12, t['ink'], 700, cls='fade', extra=d(.35)))
    x, y = 60, 256
    for k, w in enumerate(story['activates_on'][:9]):
        ww = width(w, 12, True) + 16
        if x + ww > 374:
            x, y = 60, y + 28
        if y > 284:
            break
        body.append(f'<g class="pop"{d(.4 + .05 * k)}><rect x="{x}" y="{y}" width="{ww:.0f}" height="22" rx="6" fill="{c}" fill-opacity="{t["soft"]}"/>'
                    + text(x + 8, y + 15, w, 12, t['ink'], 500, cls='mono') + '</g>')
        x += ww + 6
    for k, (a, b) in enumerate([('Tower', story['tower']), ('Makes', ', '.join(story['makes'])), ('Needs', ', '.join(story['needs']) or 'nothing'),
                                ('Next to', ', '.join(story['next_to'][:2]))]):
        body.append(text(60, 334 + 22 * k, a, 12, t['ink'], 700, cls='fade', extra=d(.7 + .05 * k))
                    + text(124, 334 + 22 * k, b if len(b) < 40 else b[:38] + '..', 12, t['ink2'], cls='mono fade', extra=d(.7 + .05 * k)))
    rows = [r for r in example.get('city', [])][:5]
    body.append(f'<g class="rise"{d(.25)}><rect x="410" y="106" width="550" height="316" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" '
                f'stroke-width="1.5"/>' + text(430, 138, 'A task raises towers', 13, c, 700)
                + text(430, 164, '"%s"' % example.get('task', ''), 15, t['ink'], 700) + '</g>')
    inner = dict(t, bg=t['tile'])
    for k, r in enumerate(rows):
        x, n = 476 + k * 104, len(r['floors'])
        fl = max(1, min(9, n))
        col = t[COLORS[k % len(COLORS)]]
        body.append(block(x, 336, 66, 33, 16 * fl + 4, col, inner, k < 2, floors=fl, cls='rise', delay=.5 + .12 * k))
        label = r['tower']
        a, b = (label, '')
        if len(label) > 15:
            cut = label.rfind(' ', 0, 16)
            cut = cut if cut > 0 else 15
            a, b = label[:cut], label[cut:].strip()
            b = b if len(b) <= 15 else b[:13] + '..'
        body.append(text(x, 376, a, 11, t['ink'], 700, 'middle', 'fade', d(.8 + .1 * k)) + text(x, 390, b, 11, t['ink'], 700, 'middle', 'fade', d(.8 + .1 * k))
                    + text(x, 408, '%d skill%s' % (n, '' if n == 1 else 's'), 11, t['ink2'], 400, 'middle', 'fade', d(.9 + .1 * k)))
    desc = ('The story of %s: the words that call it are %s. For the task "%s" the tallest towers are %s.'
            % (story['name'], ', '.join(story['activates_on'][:6]), example.get('task', ''), ', '.join(r['tower'] for r in rows)))
    return svg(1000, 442, 'The skill city', desc, ''.join(body), t)


def advantages(t, total, rel, catalog):
    e = best_engine(rel)
    used, saved = context_saved(rel, catalog)
    hold = got(rel, e, 'map', 'hold', '40')
    nothing, kw = got(rel, 'words', 'groups', 'nothing', 'nothing_empty'), got(rel, 'keyword', 'groups', 'nothing', 'nothing_empty')
    ms = got(rel, 'words', 'ms', 'typical')
    body = [header(t, 'Why use SFP', 'Too many skills crowd out your code. Too few, and your AI guesses. Measured with bench/release.py.')]
    cards = [
        (f'{saved}% less to carry', 'teal', f'{used:,} of {all_on_tokens(catalog):,} tokens', 'Your AI loads the few skills this job needs,', 'and a short map of the next 40.'),
        ('A map, not a guess', 'violet', f'{hold}% on the map' if hold else 'the next 40 skills', 'The right skill is on the 40-skill map that often.', 'Your AI reads it and can swap one in.'),
        ('Fits your project', 'sky', 'reads your manifests', 'package.json, Cargo.toml, go.mod and more, so a', 'Rust project gets Rust skills.'),
        ('Says "nothing fits"', 'rose', f'{nothing}% left empty', 'With no model, on tasks that need no skill, SFP stays', f'out of the way. Keyword search: {kw}%.'),
        ('Learns from you', 'amber', 'stays in ~/.sfp', 'Say what helped, and the weights move on your', 'machine. No task text is kept.'),
        ('Runs on your machine', 'lime', f'about {ms:.0f} ms, no model', 'Plain Python. Local models are optional, and', 'nothing is sent to pick a skill.'),
    ]
    cw, ch = 295, 148
    for i, (title, col, badge, a, b) in enumerate(cards):
        x, y, c = 40 + (i % 3) * (cw + 17.5), 108 + (i // 3) * (ch + 18), t[col]
        bw = width(badge, 12, True) + 20
        body.append(f'<g class="rise"{d(.18 + .1 * i)}><rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="14" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
                    f'<path class="draw" pathLength="1" d="M{x + 14} {y + 1} H{x + cw - 14}" stroke="{c}" stroke-width="4" stroke-linecap="round" fill="none"{d(.45 + .1 * i)}/>'
                    f'<rect x="{x + 18}" y="{y + 20}" width="{bw:.0f}" height="24" rx="12" fill="{c}" fill-opacity="{t["soft"]}"/>'
                    + text(x + 28, y + 36, badge, 12, c, 700, cls='mono') + text(x + 18, y + 72, title, 18, t['ink'], 700)
                    + text(x + 18, y + 100, a, 12, t['ink2']) + text(x + 18, y + 120, b, 12, t['ink2']) + '</g>')
    desc = 'Why use SFP: ' + '; '.join('%s (%s)' % (c[0], c[2]) for c in cards) + '.'
    return svg(1000, 444, 'Why use SFP', desc, ''.join(body), t)


def project_fit(t, same):
    body = [header(t, 'Same words, five projects', 'Real output, no model. Keyword search gives all five the same list; SFP reads the project first.')]
    body.append(f'<g class="rise"{d(.15)}><rect x="40" y="186" width="210" height="84" rx="12" fill="{t["tile"]}" stroke="{t["accent"]}" stroke-width="2"/>'
                + text(58, 216, 'You ask', 13, t['accent'], 700) + text(58, 240, '"write tests for', 15, t['ink'], 700, cls='mono')
                + text(58, 258, ' the orders"', 15, t['ink'], 700, cls='mono') + '</g>')
    body.append(f'<g class="rise"{d(.35)}><rect x="300" y="176" width="156" height="104" rx="14" fill="{t["tile"]}" stroke="{t["teal"]}" stroke-width="2"/>'
                + text(378, 220, 'SFP', 17, t['ink'], 700, 'middle') + text(378, 246, 'reads the project', 13, t['ink2'], 500, 'middle') + '</g>')
    p_in = 'M250 228 H294'
    body.append(f'<path class="draw" pathLength="1" d="{p_in}" fill="none" stroke="{t["accent"]}" stroke-width="2"{d(.5)}/>'
                f'<path class="fade" d="M300 228 l-8 -4 v8 z" fill="{t["accent"]}"{d(.9)}/>' + pulse(p_in, t['accent'], 1.2, 1.6))
    for i, (proj, picks) in enumerate(same):
        ry, c = 122 + i * 54, t[COLORS[i % len(COLORS)]]
        shown, rest = [], list(picks)
        while rest and width(', '.join(shown + [rest[0]]), 12, True) < 300:
            shown.append(rest.pop(0))
        p = f'M456 228 C500 228 500 {ry} 544 {ry}'
        body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="2"{d(.65 + .12 * i)}/>'
                    f'<path class="fade" d="M550 {ry} l-8 -4 v8 z" fill="{c}"{d(1.1 + .12 * i)}/>' + pulse(p, c, 1.5 + .28 * i, 2.0))
        body.append(f'<g class="rise"{d(.75 + .12 * i)}><rect x="552" y="{ry - 21}" width="408" height="42" rx="10" fill="{t["tile"]}" stroke="{c}" stroke-width="1.5"/>'
                    f'<rect x="562" y="{ry - 13}" width="74" height="26" rx="6" fill="{c}" fill-opacity="{t["soft"]}"/>'
                    + text(599, ry + 4, proj, 12, t['ink'], 700, 'middle') + text(648, ry + 4, ', '.join(shown) + (' +%d' % len(rest) if rest else ''), 12, t['ink'], 500, cls='mono') + '</g>')
    desc = 'For "write tests for the orders", SFP chooses: ' + '; '.join('%s: %s' % (p, ', '.join(k)) for p, k in same) + '.'
    return svg(1000, 396, 'Same words across five projects', desc, ''.join(body), t)


def taste(t, rel):
    """What learning changes for simulated learners, and how a research skill is made."""
    people = list((got(rel, 'words', 'taste') or {}).values())
    body = [header(t, 'It learns from you, and grows missing skills', 'Your feedback and history stay on your machine. A research skill is a draft until you approve it.')]
    n = people[0]['n'] if people else 0
    body.append(f'<g class="rise"{d(.15)}><rect x="40" y="106" width="450" height="296" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
                + text(60, 138, 'First pick in the format you like', 17, t['ink'], 700)
                + text(60, 158, f'{len(people)} simulated learners, {n} new tasks each, no model', 12, t['ink2'])
                + f'<rect x="60" y="172" width="12" height="10" rx="3" fill="{t["muted"]}"/>' + text(78, 181, 'Before', 12, t['ink2'])
                + f'<rect x="140" y="172" width="12" height="10" rx="3" fill="{t["accent"]}"/>' + text(158, 181, 'After it has learned', 12, t['ink'], 600) + '</g>')
    for i, p in enumerate(people[:4]):
        y, c, bw = 204 + i * 46, t[['violet', 'sky', 'teal', 'amber'][i]], 190
        body.append(text(60, y + 14, p['name'].split('(')[0].strip()[:22], 12, t['ink'], 600, cls='fade', extra=d(.3 + .1 * i)))
        body.append(f'<rect class="grow" x="212" y="{y - 2}" width="{max(2, bw * p["before"] / 100):.1f}" height="10" rx="3" fill="{t["muted"]}"{d(.45 + .1 * i)}/>')
        body.append(f'<rect class="grow" x="212" y="{y + 11}" width="{max(2, bw * p["after"] / 100):.1f}" height="12" rx="3" fill="{c}"{d(.65 + .1 * i)}/>')
        body.append(text(212 + bw * max(p['after'], p['before']) / 100 + 8, y + 18, f'{p["before"]}% to {p["after"]}%', 12, t['ink'], 700, cls='mono fade', extra=d(.95 + .1 * i)))
    body.append(f'<g class="rise"{d(.25)}><rect x="510" y="106" width="450" height="296" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
                + text(530, 138, 'A skill from new research', 17, t['ink'], 700) + text(530, 158, 'sfp research auto on: looks every few days', 12, t['ink2']) + '</g>')
    steps = [('1. Follow', 'your topics, the fastest growing first', 'rose'), ('2. Read', 'new papers from arXiv and two other indexes', 'sky'),
             ('3. Draft', 'a local model writes a cited SKILL.md', 'violet'), ('4. You approve', 'then SFP can pick it for your tasks', 'teal')]
    for i, (a, b, col) in enumerate(steps):
        sy, c = 178 + i * 54, t[col]
        body.append(f'<g class="rise"{d(.4 + .15 * i)}><rect x="530" y="{sy}" width="410" height="42" rx="8" fill="{t["bg"]}" stroke="{c}" stroke-width="1.5"/>'
                    + text(546, sy + 18, a, 13, c, 700, cls='mono') + text(546, sy + 34, b, 12, t['ink2']) + '</g>')
        if i < 3:
            p = f'M735 {sy + 42} V{sy + 54}'
            body.append(f'<path class="draw" pathLength="1" d="{p}" stroke="{c}" stroke-width="2" fill="none"{d(.7 + .15 * i)}/>' + pulse(p, c, 1.4 + .3 * i, 1.6))
    desc = ('First pick in the preferred format, before and after learning: ' + '; '.join('%s %d%% to %d%%' % (p['name'], p['before'], p['after']) for p in people)
            + '. A research skill is made by following your topics, reading new papers, drafting with a local model, and your approval.')
    return svg(1000, 424, 'How SFP learns and grows skills', desc, ''.join(body), t)


def plain_words(t, rel, asks):
    n = got(rel, 'words', 'groups', 'plain', 'n') or 0
    body = [header(t, 'When you just say what you want', f'{n} tasks in plain words, most sharing few words with the skill they need.')]
    body.append(f'<g class="rise"{d(.15)}><rect x="40" y="106" width="440" height="276" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
                + text(60, 138, 'Right skill among the picks', 17, t['ink'], 700) + text(60, 158, 'and, for SFP, on the 40-skill map your AI reads', 12, t['ink2']) + '</g>')
    for i, (eng, label, col) in enumerate(engines_shown(rel)):
        y, c, bw = 186 + i * 64, t[col], 190
        v, h = got(rel, eng, 'groups', 'plain', 'chosen') or 0, got(rel, eng, 'map', 'hold', '40')
        body.append(text(60, y + 16, label, 13, t['ink'], 700 if eng != 'keyword' else 500, cls='fade', extra=d(.3 + .1 * i)))
        body.append(f'<rect x="184" y="{y}" width="{bw}" height="20" rx="5" fill="{t["grid"]}" fill-opacity=".5"/>'
                    f'<rect class="grow" x="184" y="{y}" width="{bw * v / 100:.1f}" height="20" rx="5" fill="{c}"{d(.5 + .14 * i)}/>')
        body.append(text(184 + bw + 10, y + 15, f'{v}% picked', 12, t['ink'], 700, cls='fade', extra=d(.9 + .1 * i)))
        if h:
            body.append(f'<rect class="grow" x="184" y="{y + 25}" width="{bw * h / 100:.1f}" height="7" rx="3.5" fill="{c}" fill-opacity=".5"{d(.7 + .14 * i)}/>'
                        + text(184 + bw + 10, y + 33, f'{h:.0f}% on the map', 11, t['ink2'], cls='fade', extra=d(1.0 + .1 * i)))
    body.append(f'<g class="rise"{d(.25)}><rect x="500" y="106" width="460" height="276" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
                + text(520, 138, 'Real first picks', 17, t['ink'], 700) + text(520, 158, ('with bge-m3' if best_engine(rel) == 'meaning' else 'no model') + ', as measured, right or wrong', 12, t['ink2']) + '</g>')
    for i, (ask, picked) in enumerate(asks[:4]):
        y, c = 186 + i * 48, t[['teal', 'violet', 'amber', 'rose'][i]]
        body.append(f'<g class="rise"{d(.45 + .14 * i)}><rect x="520" y="{y - 4}" width="234" height="32" rx="7" fill="{t["bg"]}" stroke="{t["grid"]}"/>'
                    + text(530, y + 16, '"%s"' % ask, 12, t['ink2'])
                    + f'<rect x="784" y="{y - 4}" width="160" height="32" rx="7" fill="{c}" fill-opacity="{t["soft"]}" stroke="{c}" stroke-width="1.5"/>'
                    + text(864, y + 16, picked if len(picked) <= 21 else picked[:19] + '..', 12, t['ink'], 700, 'middle', cls='mono') + '</g>')
        p = f'M754 {y + 12} H778'
        body.append(f'<path class="draw" pathLength="1" d="{p}" stroke="{c}" stroke-width="2" fill="none"{d(.7 + .14 * i)}/>' + pulse(p, c, 1.5 + .3 * i, 1.8))
    desc = ('On %d plain tasks the right skill is among the picks for ' % n + '; '.join('%s %s%%' % (l, got(rel, e, 'groups', 'plain', 'chosen')) for e, l, _ in engines_shown(rel)) + '.')
    return svg(1000, 404, 'Plain words', desc, ''.join(body), t)


def results(t, rel):
    """Three panels of measured results, every engine on the same tasks."""
    body = [header(t, 'What we measured', 'Thick bar: right skill among the picks. Thin bar: right skill first. Same tasks for every engine.')]
    panels = [('plain', 'Plain words'), ('project', 'In a project'), ('nothing', 'No skill needed')]
    for p, (g, title) in enumerate(panels):
        px = 40 + p * 313
        key = 'nothing_n' if g == 'nothing' else 'n'
        n = got(rel, 'words', 'groups', g, key) or 0
        body.append(f'<g class="rise"{d(.2 + .1 * p)}><rect x="{px}" y="108" width="294" height="272" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
                    + text(px + 18, 140, title, 18, t['ink'], 700) + text(px + 18, 162, f'{n} tasks' + (', left empty on purpose' if g == 'nothing' else ''), 13, t['ink2']) + '</g>')
        for i, (eng, label, col) in enumerate(engines_shown(rel)):
            y, c, bw = 206 + i * 60, t[col], 196
            v = got(rel, eng, 'groups', g, 'nothing_empty' if g == 'nothing' else 'chosen') or 0
            f = None if g == 'nothing' else got(rel, eng, 'groups', g, 'first') or 0
            body.append(text(px + 18, y - 6, label, 13, t['ink'] if eng != 'keyword' else t['ink2'], 700 if eng != 'keyword' else 500, cls='fade', extra=d(.4)))
            body.append(f'<rect x="{px + 18}" y="{y}" width="{bw}" height="16" rx="4" fill="{t["grid"]}" fill-opacity=".6"/>'
                        f'<rect class="grow" x="{px + 18}" y="{y}" width="{max(2, bw * v / 100):.1f}" height="16" rx="4" fill="{c}"{d(.6 + .15 * i + .1 * p)}/>')
            body.append(text(px + 18 + bw + 10, y + 14, f'{v}%', 15, t['ink'], 700, cls='fade', extra=d(1.2)))
            if f is not None:
                body.append(f'<rect class="grow" x="{px + 18}" y="{y + 20}" width="{max(2, bw * f / 100):.1f}" height="5" rx="2.5" fill="{c}" fill-opacity=".55"{d(.8 + .15 * i)}/>'
                            + text(px + 18 + bw + 10, y + 28, f'{f}% first', 11, t['ink2'], cls='fade', extra=d(1.3)))
    body.append(text(40, 404, 'Never used to train SFP, but its totals were watched while it was built. Every set: bench/RESULTS.md.', 13, t['ink2'], cls='fade', extra=d(1.4)))
    desc = '; '.join('%s: %s' % (title, ', '.join('%s %s%%' % (l, got(rel, e, 'groups', g, 'nothing_empty' if g == 'nothing' else 'chosen')) for e, l, _ in engines_shown(rel)))
                     for g, title in panels) + '.'
    return svg(1000, 422, 'What we measured', desc, ''.join(body), t)


def tokens(t, rel, catalog):
    e, meta = best_engine(rel), all_on_tokens(catalog)
    stack, mp = got(rel, e, 'tokens', 'stack') or 0, got(rel, e, 'tokens', 'map') or 0
    used, saved = context_saved(rel, catalog)
    body = [header(t, 'What it costs your AI', f'{saved}% less text to hold than every skill switched on. Token counts are estimates (4 characters each).')]
    body.append(f'<g class="rise"{d(.15)}><rect x="40" y="106" width="450" height="246" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
                + text(60, 138, 'Tokens held (lower is better)', 17, t['ink'], 700) + text(60, 158, f'average over the benchmark tasks; {100.0 * meta / 200000:.0f}% of a 200k window if all are on', 12, t['ink2']) + '</g>')
    for i, (label, v, col) in enumerate([('Every skill on', meta, 'rose'), ('SFP picks', stack, 'teal'), ('SFP picks + map', used, 'violet')]):
        y, c, bw = 188 + i * 52, t[col], 180
        body.append(text(60, y + 16, label, 13, t['ink'], 700 if i else 500, cls='fade', extra=d(.3 + .1 * i)))
        body.append(f'<rect x="186" y="{y}" width="{bw}" height="22" rx="5" fill="{t["grid"]}" fill-opacity=".5"/>'
                    f'<rect class="grow" x="186" y="{y}" width="{max(6, bw * v / meta):.1f}" height="22" rx="5" fill="{c}"{d(.5 + .15 * i)}/>')
        body.append(text(186 + bw + 10, y + 16, f'{v:,}', 13, t['ink'], 700, cls='mono fade', extra=d(.9 + .1 * i)))
    body.append(f'<g class="rise"{d(.25)}><rect x="510" y="106" width="450" height="246" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
                + text(530, 138, 'Time to pick', 17, t['ink'], 700) + text(530, 158, 'one laptop, models already loaded; typical and slowest 5%', 12, t['ink2']) + '</g>')
    rows = [(l, got(rel, k, 'ms')) for k, l, _ in engines_shown(rel) if k != 'keyword']
    top = max([m['slowest_5'] for _, m in rows] or [1])
    for i, (label, m) in enumerate(rows):
        y, c, bw = 196 + i * 70, t[['sky', 'teal'][i % 2]], 200
        body.append(text(530, y - 6, label, 13, t['ink'], 700, cls='fade', extra=d(.35 + .1 * i)))
        body.append(f'<rect x="530" y="{y}" width="{bw}" height="20" rx="5" fill="{t["grid"]}" fill-opacity=".5"/>'
                    f'<rect class="grow" x="530" y="{y}" width="{max(4, bw * m["slowest_5"] / top):.1f}" height="20" rx="5" fill="{c}" fill-opacity=".4"{d(.5)}/>'
                    f'<rect class="grow" x="530" y="{y}" width="{max(4, bw * m["typical"] / top):.1f}" height="20" rx="5" fill="{c}"{d(.7)}/>')
        body.append(text(530 + bw + 10, y + 15, f'{m["typical"]:.0f} ms, slowest {m["slowest_5"]:.0f} ms', 12, t['ink'], 700, cls='mono fade', extra=d(1.0)))
    desc = f'Every skill switched on is {meta:,} tokens. SFP picks average {stack:,} tokens, {used:,} with the map: {saved}% less.'
    return svg(1000, 374, 'What it costs your AI', desc, ''.join(body), t)


def hive_architecture(t):
    body = [header(t, 'Inside the engine', 'One select_skills call, left to right. Only Meaning needs a model; without it the rest still runs.')]
    cols = [
        ('1. Readers', 'sky', [('Words', 'name, tags, description'), ('Full text', 'BM25 over SKILL.md'), ('Requests', '10 examples per skill'), ('Meaning', 'bge-m3, four views')]),
        ('2. Situation', 'amber', [('Project', 'manifests and files'), ('Phase', 'Kalman filter on work'), ('Before', 'Markov over sequences'), ('Wrong tech', 'dropped')]),
        ('3. The city', 'teal', [('Heights', 'rank on every map'), ('Neighbours', 'lend each other height'), ('Selector', 'softmax over the maps'), ('Towers', 'the next 40, grouped')]),
        ('4. Guards', 'rose', [('Nothing fits', 'says so, and why'), ('Quorum', 'in a project, signals agree'), ('Budget', 'tokens are capped'), ('Pins', 'your choices always win')]),
        ('5. Learning', 'violet', [('Feedback', 'moves map weights'), ('Taste', '30-day half-life'), ('LinUCB', 'words to skills'), ('Research', 'drafts you approve')]),
    ]
    cw, ch, top, gap = 172, 290, 108, 15
    for i, (title, col, items) in enumerate(cols):
        x, c = 40 + i * (cw + gap), t[col]
        g = [f'<g class="rise"{d(.18 + .12 * i)}><rect x="{x}" y="{top}" width="{cw}" height="{ch}" rx="12" fill="{t["tile"]}" stroke="{c}" stroke-width="1.5"/>'
             f'<path class="draw" pathLength="1" d="M{x + 12} {top + 1} H{x + cw - 12}" stroke="{c}" stroke-width="4" stroke-linecap="round" fill="none"{d(.45 + .12 * i)}/>'
             + text(x + 14, top + 30, title, 15, c, 700)]
        for k, (a, b) in enumerate(items):
            iy = top + 52 + k * 56
            g.append(f'<rect x="{x + 10}" y="{iy}" width="{cw - 20}" height="46" rx="7" fill="{t["bg"]}" stroke="{t["grid"]}"/>'
                     + text(x + 18, iy + 19, a, 13, t['ink'], 700) + text(x + 18, iy + 36, b, 11, t['ink2']))
        body.append(''.join(g) + '</g>')
        if i < len(cols) - 1:
            x1, x2, my = x + cw, x + cw + gap, top + ch / 2
            p = f'M{x1} {my} H{x2 - 5}'
            body.append(f'<path class="draw" pathLength="1" d="{p}" stroke="{c}" stroke-width="2" fill="none"{d(.7 + .12 * i)}/>'
                        f'<path class="fade" d="M{x2} {my} l-7 -4 v8 z" fill="{c}"{d(1.0 + .12 * i)}/>' + pulse(p, c, 1.5 + .25 * i, 1.8))
    ly = top + ch + 36
    loop = f'M874 {top + ch + 2} V{ly} H500 V{top + ch + 8}'
    body.append(f'<path class="draw" pathLength="1" d="{loop}" fill="none" stroke="{t["accent"]}" stroke-width="2"{d(1.8)}/>'
                f'<path class="fade" d="M500 {top + ch + 2} l-5 8 h10 z" fill="{t["accent"]}"{d(2.4)}/>')
    body.append(text(486, ly + 4, 'feedback moves the weights in ~/.sfp; no task text is stored', 13, t['accent'], 600, 'end', 'fade', d(2.2)))
    desc = 'Inside the engine: ' + '; '.join('%s: %s' % (c[0], ', '.join(a for a, _ in c[2])) for c in cols) + '.'
    return svg(1000, 462, 'Inside the engine', desc, ''.join(body), t)


# ----------------------------------------------------------------- drawings


def results_rounds(t, dz):
    """Animated dual-panel illustration: Blind UI Design Review Rounds (left) + Unseen Tool Verification Checks (right)."""
    sfp_r = dz.get('sfp', {}).get('rounds', 2.8)
    pick_r = dz.get('picked', {}).get('rounds', 3.4)
    base_r = dz.get('baseline', {}).get('rounds', 3.7)
    sfp_s = dz.get('sfp', {}).get('shipped', 8)
    sfp_n = dz.get('sfp', {}).get('n', 9)
    pick_s = dz.get('picked', {}).get('shipped', 6)
    base_s = dz.get('baseline', {}).get('shipped', 5)

    body = [header(t, "Does it make the agent's output better?",
                   'Blind design reviews and unseen CLI verification checks (docs/EFFECT.md).')]
    # Left panel: Design review rounds
    body.append(
        f'<g class="rise"{d(.15)}>'
        f'<rect x="40" y="106" width="450" height="246" rx="12" fill="{t["tile"]}" stroke="{t["grid"]}" stroke-width="1.5"/>'
        + text(60, 138, '1. Blind UI Design Reviews (Lower is Better)', 17, t['ink'], 700)
        + text(60, 158, f'Review rounds until a blind judge accepts the page, {sfp_n} pages each', 12, t['ink2'])
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
        bw = 126
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
    body = [header(t, f'{total:,} skills in {len(per)} categories & 121 bundles',
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
    body = [header(t, 'Bundles for UI work',
                   'Skills that work well together, in the order to use them.')]
    tracks = [
        ('Accessible form bundle', 'rose', 150, [
            ('frontend-a11y', 'semantic HTML & ARIA'),
            ('ux-writing', 'concise microcopy'),
            ('react-patterns', 'state & composition'),
            ('accessibility-audit', 'WCAG & keyboard check'),
        ]),
        ('Ship a page bundle', 'violet', 265, [
            ('design-taste-frontend', 'hierarchy & spacing'),
            ('impeccable', 'editorial polish'),
            ('accessibility-audit', 'WCAG & keyboard check'),
            ('break-ui', 'layout stress test'),
        ]),
    ]
    for tr, (label, col, y, nodes) in enumerate(tracks):
        c = t[col]
        body.append(text(40, y - 34, label, 13, c, 700, cls='fade', extra=d(.15 + .2 * tr)))
        w = 206
        for i, (name, sub) in enumerate(nodes):
            x = 40 + i * 238
            disp = name if len(name) <= 19 else name[:18] + '..'
            body.append(f'<g class="rise"{d(.2 + .12 * i + .2 * tr)}><rect x="{x}" y="{y - 24}" width="{w}" height="58" '
                        f'rx="12" fill="{t["tile"]}" stroke="{c}" stroke-width="2"/>'
                        f'<circle cx="{x + 22}" cy="{y + 5}" r="11" fill="{c}"/>'
                        + text(x + 22, y + 9, str(i + 1), 11, '#ffffff' if t is THEMES['light'] else t['bg'], 700, 'middle')
                        + text(x + 40, y, disp, 12, t['ink'], 700, cls='mono')
                        + text(x + 40, y + 18, sub, 12, t['ink2']) + '</g>')
            if i < len(nodes) - 1:
                x1, x2 = x + w, x + 238
                p = f'M{x1} {y + 5} H{x2 - 6}'
                body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="2"{d(.6 + .15 * i + .2 * tr)}/>'
                            f'<path class="fade" d="M{x2} {y + 5} l-8 -4 v8 z" fill="{c}"{d(1.1 + .15 * i + .2 * tr)}/>')
                body.append(pulse(p, c, 1.8 + .35 * i + .4 * tr, 1.8))
    desc = ('Two bundles: Accessible form (frontend-a11y, ux-writing, react-patterns, accessibility-audit) and Ship a page '
            '(design-taste-frontend, impeccable, accessibility-audit, break-ui).')
    return svg(1000, 355, 'Bundles for UI work', desc, ''.join(body), t)


def growth_flow(t):
    """Dedicated animated workflow for Business, Marketing, Fundraising & Content."""
    body = [header(t, 'Bundles for business and content',
                   'Skills that work well together, in the order to use them.')]
    tracks = [
        ('Fundraise bundle', 'amber', 150, [
            ('market-research', 'TAM & positioning'),
            ('investor-materials', 'deck & narrative'),
            ('investor-outreach', 'warm & cold outreach'),
        ]),
        ('Write and promote bundle', 'teal', 265, [
            ('article-writing', 'proof-led long-form'),
            ('seo', 'intent & schema audit'),
            ('content-engine', 'multi-channel launch'),
            ('brand-voice', 'your own voice'),
        ]),
    ]
    for tr, (label, col, y, nodes) in enumerate(tracks):
        c = t[col]
        body.append(text(40, y - 34, label, 13, c, 700, cls='fade', extra=d(.15 + .2 * tr)))
        w = 206
        for i, (name, sub) in enumerate(nodes):
            x = 40 + i * 238
            disp = name if len(name) <= 19 else name[:18] + '..'
            body.append(f'<g class="rise"{d(.2 + .12 * i + .2 * tr)}><rect x="{x}" y="{y - 24}" width="{w}" height="58" '
                        f'rx="12" fill="{t["tile"]}" stroke="{c}" stroke-width="2"/>'
                        f'<circle cx="{x + 22}" cy="{y + 5}" r="11" fill="{c}"/>'
                        + text(x + 22, y + 9, str(i + 1), 11, '#ffffff' if t is THEMES['light'] else t['bg'], 700, 'middle')
                        + text(x + 40, y, disp, 12, t['ink'], 700, cls='mono')
                        + text(x + 40, y + 18, sub, 12, t['ink2']) + '</g>')
            if i < len(nodes) - 1:
                x1, x2 = x + w, x + 238
                p = f'M{x1} {y + 5} H{x2 - 6}'
                body.append(f'<path class="draw" pathLength="1" d="{p}" fill="none" stroke="{c}" stroke-width="2"{d(.6 + .15 * i + .2 * tr)}/>'
                            f'<path class="fade" d="M{x2} {y + 5} l-8 -4 v8 z" fill="{c}"{d(1.1 + .15 * i + .2 * tr)}/>')
                body.append(pulse(p, c, 1.8 + .35 * i + .4 * tr, 1.8))
    desc = ('Two bundles: Fundraise (market-research, investor-materials, investor-outreach) and Write and promote '
            '(article-writing, seo, content-engine, brand-voice).')
    return svg(1000, 355, 'Bundles for business and content', desc, ''.join(body), t)


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


ASKS = ('make the login not get hacked', 'test all the buttons on my site', 'my page loads too slowly', 'turn my notes into a slide deck')


def main():
    catalog = load_catalog()
    total, ncats = len(catalog), len({s['category'] for s in catalog})
    rel = release()
    # The examples are the ones the benchmark recorded, so a picture, the README and the results always agree.
    asked = got(rel, best_engine(rel), 'asks') or []
    hero_example = asked[0] if asked else (hive(ASKS[0]) or {'stack': []})
    hero_example.setdefault('task', ASKS[0])
    term_example = hive('build a signup page with a form, store users in postgres, '
                        'add end to end tests and deploy it with docker')
    term_example.setdefault('task', 'build a signup page')
    city_example = hero_example
    asks = [(a['task'], a['lead'] or 'no skill selected') for a in asked]
    same = ask_python(SAME) or []
    story = ask_python(STORY, 'react-performance')
    dz = design_numbers()
    for name, t in THEMES.items():
        hero_svg = hero(t, total, ncats, hero_example, catalog, rel)
        write('banner', name, hero_svg)
        write('hero', name, hero_svg)
        write('pipeline', name, pipeline(t))
        if story:
            write('city', name, city(t, story, city_example))
        write('project-fit', name, project_fit(t, same))
        write('library', name, library(t, catalog))
        write('roles', name, roles(t, catalog))
        write('install-steps', name, install_steps(t))
        write('terminal', name, terminal(t, term_example))
        write('ui-flow', name, ui_flow(t))
        write('growth-flow', name, growth_flow(t))
        write('results-rounds', name, results_rounds(t, dz))
        write('hive-architecture', name, hive_architecture(t))
        write('tools', name, tools(t))
        if rel.get('engines', {}).get('words'):
            write('advantages', name, advantages(t, total, rel, catalog))
            write('taste', name, taste(t, rel))
            write('plain-words', name, plain_words(t, rel, asks))
            write('results', name, results(t, rel))
            write('tokens', name, tokens(t, rel, catalog))
    print('README art written to assets/')


if __name__ == '__main__':
    main()
