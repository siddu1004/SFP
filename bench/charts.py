#!/usr/bin/env python3
"""Draw the README's result charts as SVG, in the banner's colours, from the saved results.

  python3 bench/charts.py          writes assets/results-*-light.svg and -dark.svg

Numbers come from bench/design/results/*.json and `sfp_hive.py evaluate`, so the charts change only when the results do.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
# The banner's colours. The muted bars are the de-emphasis gray, below 3:1 on purpose, so every bar carries its value.
THEMES = {
    'light': {'bg': '#f4f1ea', 'ink': '#1a1d21', 'ink2': '#565c64', 'accent': '#0f766e', 'muted': '#a8a190',
              'grid': '#e2ddd2', 'tile': '#fbf9f4'},
    'dark': {'bg': '#12171f', 'ink': '#e6edf3', 'ink2': '#9aa4b0', 'accent': '#2dd4bf', 'muted': '#4a5768',
             'grid': '#2c3643', 'tile': '#18202b'},
}


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def text(x, y, s, size, fill, weight=400, anchor='start'):
    return ('<text x="%s" y="%s" font-family="%s" font-size="%s" font-weight="%s" fill="%s" text-anchor="%s">%s</text>'
            % (x, y, FONT, size, weight, fill, anchor, esc(s)))


def bar(x, y, w, h, fill):
    """A horizontal bar anchored at the baseline (square left end), with a 4px rounded data end."""
    r = min(4, w / 2, h / 2)
    return ('<path d="M%.1f %.1f H%.1f Q%.1f %.1f %.1f %.1f V%.1f Q%.1f %.1f %.1f %.1f H%.1f Z" fill="%s"/>'
            % (x, y, x + w - r, x + w, y, x + w, y + r, y + h - r, x + w, y + h, x + w - r, y + h, x, fill))


def svg(w, h, title, desc, body, t):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" '
            'aria-labelledby="t d"><title id="t">%s</title><desc id="d">%s</desc>'
            '<rect width="%d" height="%d" rx="16" fill="%s"/>%s</svg>\n'
            % (w, h, w, h, esc(title), esc(desc), w, h, t['bg'], body))


def bars_chart(title, sub, rows, vmax, fmt, note, t, w=1280):
    """rows: [(label, value, highlight, side_note)]. One series, so no legend: the title names it."""
    top, row_h, gap, left, right = 132, 46, 22, 370, 250
    h = top + len(rows) * (row_h + gap) + 70
    span = w - left - right
    out = [text(64, 64, title, 30, t['ink'], 600), text(64, 100, sub, 19, t['ink2'])]
    for i in range(6):
        gx = left + span * i / 5
        out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1"/>'
                   % (gx, top - 10, gx, top + len(rows) * (row_h + gap) - gap + 10, t['grid']))
    for i, (label, value, hi, side) in enumerate(rows):
        y = top + i * (row_h + gap)
        out.append(text(64, y + row_h / 2 + 7, label, 21, t['ink'], 600 if hi else 400))
        bw = max(6, span * value / vmax)
        out.append(bar(left, y, bw, row_h, t['accent'] if hi else t['muted']))
        out.append(text(left + bw + 14, y + row_h / 2 + 8, fmt(value), 22, t['ink'], 700 if hi else 500))
        if side:
            out.append(text(w - 64, y + row_h / 2 + 7, side, 18, t['ink2'], 400, 'end'))
    out.append(text(64, h - 30, note, 16, t['ink2']))
    return svg(w, h, title, sub + ' ' + note, ''.join(out), t)


def tiles(items, t, w=1280, h=250):
    """Hero numbers: one figure per tile, its comparison underneath in text."""
    n, pad, gap = len(items), 32, 20
    tw = (w - 2 * pad - (n - 1) * gap) / n
    out = []
    for i, (big, line1, line2) in enumerate(items):
        x = pad + i * (tw + gap)
        out.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" rx="12" fill="%s"/>' % (x, pad, tw, h - 2 * pad, t['tile']))
        out.append(text(x + 28, pad + 78, big, 54, t['accent'], 700))
        out.append(text(x + 28, pad + 122, line1, 20, t['ink'], 600))
        out.append(text(x + 28, pad + 152, line2, 17, t['ink2']))
    return svg(w, h, 'SFP in numbers', '; '.join('%s %s, %s' % it for it in items), ''.join(out), t)


def design_numbers():
    runs = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'bench', 'design', 'results', '*.json'))):
        with open(f) as fh:
            runs += json.load(fh)
    out = {}
    for arm in ('baseline', 'sfp', 'picked'):
        xs = [r for r in runs if r['arm'] == arm]
        out[arm] = {'n': len(xs), 'shipped': sum(1 for r in xs if r['rounds_to_ship']),
                    'rounds': sum((r['rounds_to_ship'] or 5) for r in xs) / len(xs)}
    return out


def selection_numbers():
    with tempfile.TemporaryDirectory() as data:
        out = subprocess.run([sys.executable, os.path.join(ROOT, 'mcp', 'sfp_hive.py'), 'evaluate'], capture_output=True,
                             text=True, env=dict(os.environ, SFP_DATA_DIR=data), check=True).stdout
    d = json.loads(out)
    return {k: d['fresh_' + k]['hit'] for k in ('select', 'v1', 'search')}, d['fresh_select']['n']


def write(name, body):
    with open(os.path.join(ROOT, 'assets', name), 'w', encoding='utf-8') as f:
        f.write(body)


def main():
    dz = design_numbers()
    sel, n_fresh = selection_numbers()
    with open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8') as f:
        total = len(json.load(f)['skills'])
    n_runs = sum(v['n'] for v in dz.values())
    for name, t in THEMES.items():
        rows = [('SFP picks the skills', dz['sfp']['rounds'], True, '%d of %d pages shipped' % (dz['sfp']['shipped'], dz['sfp']['n'])),
                ('No skills', dz['baseline']['rounds'], False, '%d of %d shipped' % (dz['baseline']['shipped'], dz['baseline']['n'])),
                ('Hand-picked design skills', dz['picked']['rounds'], False, '%d of %d shipped' % (dz['picked']['shipped'], dz['picked']['n']))]
        write('results-rounds-%s.svg' % name, bars_chart(
            'Fewer rounds of "make it better"', 'Review rounds until a design reviewer would ship the page. Fewer is better.',
            rows, 5, lambda v: '%.1f rounds' % v,
            '%d runs on 3 pages. Sonnet builds; Opus reviews screenshots without knowing which arm made them. '
            'Never shipped counts as 5. A small first sample.' % n_runs, t))
        rows = [('SFP hive', sel['select'] * 100, True, ''), ('Earlier engine', sel['v1'] * 100, False, ''),
                ('Plain search', sel['search'] * 100, False, '')]
        write('results-accuracy-%s.svg' % name, bars_chart(
            'The right skill, on tasks it has never seen',
            'Share of %d held-out tasks where the stack holds a skill a person marked correct.' % n_fresh,
            rows, 100, lambda v: '%.0f%%' % v,
            'Tasks written before scoring and scored once. Reproduce: python3 mcp/sfp_hive.py evaluate', t))
        write('results-numbers-%s.svg' % name, tiles([
            ('%.0f%%' % (sel['select'] * 100), 'right skill on unseen tasks', 'plain search: %.0f%% (22 tasks)' % (sel['search'] * 100)),
            ('%d of %d' % (dz['sfp']['shipped'], dz['sfp']['n']), 'pages shipped with SFP',
             'without skills: %d of %d (small first test)' % (dz['baseline']['shipped'], dz['baseline']['n'])),
            ('%d' % total, 'skills, sorted by what you build', 'your agent loads only the few it needs')], t))
    print('wrote assets/results-{numbers,rounds,accuracy}-{light,dark}.svg')


if __name__ == '__main__':
    main()
