#!/usr/bin/env python3
"""Draw the SFP banner from catalog.json.

Writes assets/banner-light.svg and assets/banner-dark.svg. The picture is the
product's idea: a shelf with one group of spines per category (group width
follows the category's skill count) and one lit spine that a single line from
the `sfp` wordmark reaches. Run by scripts/sync.py; safe to run alone.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 300
BASE = 262          # shelf line
SHELF_X0, SHELF_X1 = 600, 1232
GROUP_GAP = 12
SPINE_W = 2.6
LIT_CATEGORY = 'agents'

THEMES = {
    'light': dict(bg='#f4f1ea', text='#1a1d21', muted='#565c64', tile_a='#cdc7b8', tile_b='#b8b1a0', accent='#0f766e'),
    'dark':  dict(bg='#12171f', text='#e6edf3', muted='#9aa4b0', tile_a='#2c3643', tile_b='#3d4959', accent='#2dd4bf'),
}
FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"


def spine_height(group, i):
    # Deterministic and varied; no random module so reruns produce identical files.
    return 78 + ((group * 37 + i * 61 + (group * i) % 7 * 11) % 104)


def layout(counts):
    """Return one list of (x, height) spines per group, fitted to the shelf width."""
    spines = [max(1, math.ceil(c / 5)) for c in counts]
    n = sum(spines)
    avail = (SHELF_X1 - SHELF_X0) - GROUP_GAP * (len(counts) - 1)
    pitch = min(4.2, avail / n)
    x, groups = SHELF_X0, []
    for g, k in enumerate(spines):
        row = []
        for i in range(k):
            row.append((x, spine_height(g, i)))
            x += pitch
        groups.append(row)
        x += GROUP_GAP
    return groups


def render(theme, counts, names, total):
    t = THEMES[theme]
    groups = layout(counts)
    lit_g = names.index(LIT_CATEGORY)
    lit_i = len(groups[lit_g]) // 2
    lit_x = groups[lit_g][lit_i][0]
    lit_top = BASE - 206
    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">')
    a('  <title id="t">SFP: Skills for Productivity</title>')
    a(f'  <desc id="d">A shelf of {total} skills in {len(names)} groups. One line from the sfp wordmark reaches the one skill the agent needs.</desc>')
    a(f'  <rect width="{W}" height="{H}" rx="16" fill="{t["bg"]}"/>')
    for g, row in enumerate(groups):
        fill = t['tile_a'] if g % 2 == 0 else t['tile_b']
        for i, (x, h) in enumerate(row):
            if g == lit_g and i == lit_i:
                continue
            a(f'  <rect x="{x:.1f}" y="{BASE - h}" width="{SPINE_W}" height="{h}" fill="{fill}"/>')
    a(f'  <rect x="{SHELF_X0 - 8}" y="{BASE}" width="{SHELF_X1 - SHELF_X0 + 16}" height="3" fill="{t["tile_b"]}"/>')
    a(f'  <rect x="{lit_x:.1f}" y="{lit_top}" width="{SPINE_W + 1.4}" height="{BASE - lit_top}" fill="{t["accent"]}"/>')
    a(f'  <path d="M444 124 H520 V34 H{lit_x + 1.3:.1f} V{lit_top}" fill="none" stroke="{t["accent"]}" stroke-width="3" stroke-linejoin="round"/>')
    a(f'  <circle cx="444" cy="124" r="7" fill="{t["accent"]}"/>')
    # wordmark drawn as strokes so it never depends on an installed font
    a(f'  <g fill="none" stroke="{t["text"]}" stroke-width="24" stroke-linejoin="miter" stroke-linecap="butt">')
    a('    <path d="M152 76 H100 A24 24 0 0 0 100 124 H128 A24 24 0 0 1 128 172 H76"/>')
    a('    <path d="M208 172 V76 H284 M208 124 H268"/>')
    a('    <path d="M340 172 V76 H386 A24 24 0 0 1 386 124 H340"/>')
    a('  </g>')
    a(f'  <text x="64" y="232" font-family="{FONT}" font-size="36" font-weight="600" fill="{t["text"]}">Skills for Productivity</text>')
    a(f'  <text x="64" y="272" font-family="{FONT}" font-size="26" fill="{t["muted"]}">{total} skills. The hive picks the few you need, and learns.</text>')
    a('</svg>')
    return '\n'.join(out) + '\n'


def main():
    cat = json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))
    names = [n for n, v in cat['categories'].items() if v['skills']]
    counts = [cat['categories'][n]['skills'] for n in names]
    total = sum(counts)
    os.makedirs(os.path.join(ROOT, 'assets'), exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(ROOT, 'assets', f'banner-{theme}.svg'), 'w', encoding='utf-8') as f:
            f.write(render(theme, counts, names, total))
    print(f'banner: {total} skills, {len(names)} groups')


if __name__ == '__main__':
    main()
