#!/usr/bin/env python3
"""Draw the README's pictures as SVG, in the banner's colours, from the saved results.

  python3 bench/charts.py          writes assets/*-light.svg and -dark.svg, and bench/charts/*

Numbers come from bench/results/*.json (written by bench/run_all.py) and bench/design/results/*.json, so the charts
change only when the results do. Text is sized for a 1000-wide picture shown about 830 wide on GitHub, and every label
leaves room for a wider font, because the reader's system font draws it.
"""
import glob
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assets')
CHARTS = os.path.join(ROOT, 'bench', 'charts')
FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
# The banner's colours. The muted bars are the de-emphasis gray, below 3:1 on purpose, so every bar carries its value.
THEMES = {
    'light': {'bg': '#f4f1ea', 'ink': '#1a1d21', 'ink2': '#565c64', 'accent': '#0f766e', 'muted': '#a8a190',
              'grid': '#e2ddd2', 'tile': '#fbf9f4', 'on_accent': '#ffffff'},
    'dark': {'bg': '#12171f', 'ink': '#e6edf3', 'ink2': '#9aa4b0', 'accent': '#2dd4bf', 'muted': '#4a5768',
             'grid': '#2c3643', 'tile': '#18202b', 'on_accent': '#06201d'},
}
HELD_OUT = ('fresh', 'reworded_holdout', 'plain_words_holdout2')


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


def card(x, y, w, h, t, stroke=None):
    edge = ' stroke="%s" stroke-width="2"' % stroke if stroke else ''
    return '<rect x="%s" y="%s" width="%s" height="%s" rx="12" fill="%s"%s/>' % (x, y, w, h, t['tile'], edge)


def arrow(x1, y1, x2, y2, color):
    head = '<path d="M%s %s l-9 -5 v10 z" fill="%s"/>' % (x2, y2, color)
    return '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="2"/>%s' % (x1, y1, x2 - 8, y2, color, head)


def svg(w, h, title, desc, body, t):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" '
            'aria-labelledby="t d"><title id="t">%s</title><desc id="d">%s</desc>'
            '<rect width="%d" height="%d" rx="16" fill="%s"/>%s</svg>\n'
            % (w, h, w, h, esc(title), esc(desc), w, h, t['bg'], body))


def bars_chart(title, sub, rows, vmax, fmt, notes, t, w=1000, left=330, right=190):
    """rows: [(label, value, highlight, side_note)]. One series, so no legend: the title names it."""
    top, row_h, gap = 112, 38, 16
    span = w - left - right
    bottom = top + len(rows) * (row_h + gap) - gap
    h = bottom + 28 + 24 * len(notes) + 14
    out = [text(40, 50, title, 26, t['ink'], 700), text(40, 80, sub, 16, t['ink2'])]
    for i, (label, value, hi, side) in enumerate(rows):
        y = top + i * (row_h + gap)
        out.append(text(40, y + row_h / 2 + 6, label, 17, t['ink'], 700 if hi else 400))
        bw = max(6, span * value / vmax)
        out.append(bar(left, y, bw, row_h, t['accent'] if hi else t['muted']))
        out.append(text(left + bw + 12, y + row_h / 2 + (0 if side else 6), fmt(value), 18, t['ink'], 700 if hi else 500))
        if side:
            out.append(text(left + bw + 12, y + row_h / 2 + 17, side, 13, t['ink2']))
    for i, note in enumerate(notes):
        out.append(text(40, bottom + 34 + 24 * i, note, 14, t['ink2']))
    return svg(w, h, title, sub + ' ' + ' '.join(notes), ''.join(out), t)


def wilson(p, n, z=1.96):
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - m, c + m


def pooled(results, engine, key='hit'):
    """An engine's share over all the held-out tasks together, with the task count."""
    suites = results[engine]['suites']
    if 'final_heldout_plain_v2' in suites:
        target_suites = ('final_heldout_plain_v2', 'final_heldout_project_v2', 'final_heldout_reworded_v2')
    elif 'final_heldout_plain' in suites:
        target_suites = ('final_heldout_plain', 'final_heldout_project', 'final_heldout_reworded')
    else:
        target_suites = HELD_OUT
    valid_suites = [s for s in target_suites if s in suites]
    n = sum(suites[s]['n'] for s in valid_suites)
    return sum(suites[s][key] * suites[s]['n'] for s in valid_suites) / n, n


def headline(results, t):
    rows = []
    for engine, label in (('keyword', 'Keyword search'), ('v1', 'SFP, first version'), ('hive_words', 'SFP, words only'),
                          ('hive_meaning', '+ understands meaning'), ('hive_rerank_auto', '+ a model double-checks')):
        p, n = pooled(results, engine)
        lo, hi = wilson(p, n)
        rows.append((label, p * 100, engine == 'hive_rerank_auto', 'likely between %d%% and %d%%' % (round(lo * 100), round(hi * 100))))
    return bars_chart('How often the right skill is chosen',
                      '%d tasks SFP had never seen. None were used to tune it. Higher is better.' % n,
                      rows, 100, lambda v: '%.0f%%' % v,
                      ['Counts a task as right when the chosen skills include one a person marked correct.',
                       'The two "+" rows use models on your own machine. Full method: bench/RESULTS.md'], t)


def plain_words(results, t):
    if 'final_heldout_plain_v2' in results['keyword']['suites']:
        s = 'final_heldout_plain_v2'
    elif 'final_heldout_plain' in results['keyword']['suites']:
        s = 'final_heldout_plain'
    else:
        s = 'plain_words_holdout2'
    rows = [('Keyword search', results['keyword']['suites'][s]['hit'] * 100, False, None),
            ('SFP, words only', results['hive_words']['suites'][s]['hit'] * 100, False, None),
            ('+ understands meaning', results['hive_meaning']['suites'][s]['hit'] * 100, False, None),
            ('+ a model double-checks', results['hive_rerank_auto']['suites'][s]['hit'] * 100, True, None)]
    n = results['keyword']['suites'][s]['n']
    return bars_chart('When you describe the problem in plain words',
                      '%d tasks written the way a beginner types them. Higher is better.' % n,
                      rows, 100, lambda v: '%.0f%%' % v,
                      ['For example: "make the login not get hacked", "test all the buttons on my website".'], t)


def taste(data, t):
    tasks = data['taste_eval']
    names = {'visual_animation': 'Learns from animation', 'reader_text': 'Learns from reading',
             'hands_on_code': 'Learns by coding', 'video_producer': 'Makes videos'}
    w, left, right, row_h, gap, top = 1000, 270, 130, 22, 22, 140
    span = w - left - right
    title = 'SFP learns which format helps you'
    sub = 'How often the first pick is in the format this person likes, on topics new to them.'
    out = [text(40, 50, title, 26, t['ink'], 700), text(40, 80, sub, 16, t['ink2'])]
    out.append(bar(40, 100, 18, 14, t['muted']) + text(66, 112, 'Brand new user', 14, t['ink2']))
    out.append(bar(220, 100, 18, 14, t['accent']) + text(246, 112, 'After SFP has learned their taste', 14, t['ink2']))
    keys = [k for k in names if k in tasks]
    for i, key in enumerate(keys):
        p = tasks[key]
        y = top + i * (2 * row_h + 4 + gap)
        out.append(text(40, y + row_h + 8, names[key], 17, t['ink']))
        for j, (val, fill, weight) in enumerate(((p['cold_start_form_right'], t['muted'], 500),
                                                 (p['with_taste_form_right'], t['accent'], 700))):
            ry = y + j * (row_h + 4)
            bw = max(6, span * val)
            out.append(bar(left, ry, bw, row_h, fill))
            out.append(text(left + bw + 10, ry + row_h - 5, '%.0f%%' % (val * 100), 16, t['ink'], weight))
    bottom = top + len(keys) * (2 * row_h + 4 + gap) - gap
    follow = sum(tasks[k]['explicit_override_respected'] for k in keys) / len(keys)
    notes = ['Simulated people, with a history of skills they liked. 40 new tasks in all.',
             'When a task names a format ("as text"), SFP followed it on %.0f%% of these tasks.' % (follow * 100)]
    for i, note in enumerate(notes):
        out.append(text(40, bottom + 34 + 24 * i, note, 14, t['ink2']))
    h = bottom + 34 + 24 * len(notes) + 4
    return svg(w, h, title, sub + ' ' + ' '.join(notes), ''.join(out), t)


def tokens(data, t):
    meta = data['catalog_meta_tokens']
    bench = data['results']['hive_rerank_auto']['suites']['bench']
    used = bench['avg_tokens']
    rows = [('Every skill, always on', meta, False, None), ('Only what SFP picked', used, True, None)]
    return bars_chart('What your AI has to keep in mind',
                      'Words it must hold (in tokens) before it can start on your code. Lower is better.',
                      rows, meta, lambda v: format(int(v), ','),
                      ['Measured over %d tasks: %.0f%% less. Every skill description against the full text of the skills picked.' % (bench['n'], 100 - 100.0 * used / meta)],
                      t, right=160)


def latency(results, t):
    rows = []
    for engine, label in (('keyword', 'Keyword search'), ('hive_words', 'SFP, words only'), ('hive_meaning', '+ understands meaning'),
                          ('hive_rerank_auto', '+ a model double-checks')):
        b = results[engine]['suites']['bench']
        rows.append((label, b['latency_p95_ms'], engine == 'hive_rerank_auto', 'typical %.0f ms' % b['latency_p50_ms']))
    return bars_chart('How long a choice takes', 'Slowest 5% of tasks (p95), and the typical task under it. Lower is better.',
                      rows, 2000, lambda v: '%.0f ms' % v,
                      ['The model is only asked when the words are unsure, so most tasks stay fast.'], t, right=210)


def flow(total, t):
    """The whole idea for someone new: five steps and the loop back."""
    w, h, top, ch, cw, gap, x0 = 1000, 330, 104, 150, 172, 15, 40
    title = 'How SFP works'
    sub = 'You keep talking to your AI as usual. SFP hands it the right instructions first.'
    steps = [('1', 'You ask', ['in your own', 'words'], False),
             ('2', 'SFP reads', ['your words, your', 'project, and what', 'helped you before'], False),
             ('3', 'It picks', ['a few of %s' % format(total, ','), 'skills that fit', 'this task'], True),
             ('4', 'Your AI works', ['following those', 'skills, and says', 'why it chose them'], False),
             ('5', 'You say', ['helped, or', 'did not help'], False)]
    out = [text(40, 50, title, 26, t['ink'], 700), text(40, 80, sub, 16, t['ink2'])]
    for i, (num, head, lines, hi) in enumerate(steps):
        x = x0 + i * (cw + gap)
        out.append(card(x, top, cw, ch, t, stroke=t['accent'] if hi else t['grid']))
        out.append('<circle cx="%d" cy="%d" r="14" fill="%s"/>' % (x + 28, top + 30, t['accent'] if hi else t['muted']))
        out.append(text(x + 28, top + 35, num, 15, t['on_accent'] if hi else t['bg'], 700, 'middle'))
        out.append(text(x + 50, top + 36, head, 17, t['ink'], 700))
        for j, line in enumerate(lines):
            out.append(text(x + 16, top + 72 + j * 22, line, 15, t['ink2']))
        if i:
            out.append(arrow(x - gap + 1, top + ch / 2, x - 1, top + ch / 2, t['accent']))
    # The loop from step 5 back to step 2.
    x2, x5, ly = x0 + (cw + gap) + cw / 2, x0 + 4 * (cw + gap) + cw / 2, top + ch + 34
    out.append('<path d="M%s %s V%s H%s V%s" fill="none" stroke="%s" stroke-width="2" stroke-dasharray="6 5"/>'
               % (x5, top + ch + 2, ly, x2, top + ch + 10, t['accent']))
    out.append('<path d="M%s %s l-5 9 h10 z" fill="%s"/>' % (x2, top + ch + 1, t['accent']))
    mid = (x2 + x5) / 2
    out.append('<rect x="%s" y="%s" width="370" height="26" fill="%s"/>' % (mid - 185, ly - 13, t['bg']))
    out.append(text(mid, ly + 5, 'It learns, so the next choice fits you better', 15, t['accent'], 600, 'middle'))
    return svg(w, h, title, sub + ' You ask, SFP reads your words and project, picks a few skills, your AI follows them, you say if they helped, and it learns.',
               ''.join(out), t)


def architecture(t):
    """The pipeline for someone who wants to know what actually runs."""
    w, h = 1000, 640
    title = 'Inside the hive'
    sub = 'One select_skills call. Models are optional: without them the rest still works.'
    out = [text(40, 50, title, 26, t['ink'], 700), text(40, 80, sub, 16, t['ink2'])]
    cols = [
        (28, 'Reads', False, [
            ('The task', 'text, split into stems'),
            ('Project files', 'manifests and sources'),
            ('Work phase', 'Kalman filter on activity'),
            ('What came before', 'Markov skill sequences'),
            ('Your feedback', 'stored as numbers')]),
        (268, 'Signals vote', False, [
            ('Words', 'inverted word index'),
            ('Meaning (optional)', 'bge-m3, cosine over text'),
            ('', 'and example requests'),
            ('Project fit', 'wrong technology is out'),
            ('Phase and category', 'does it suit the job'),
            ('Your role', 'small push from the repo')]),
        (508, 'Choose', True, [
            ('Quorum', 'needs several backers'),
            ('Rerank (optional)', 'model reads top 20, only'),
            ('', 'if words weak, no fit'),
            ('Skill cards', 'job, output, style, depth'),
            ('Taste and model', 'liked formats, LinUCB'),
            ('Roles', 'few per job, no twins')]),
        (748, 'Hands over', False, [
            ('Ordered skills', 'with the reasons why'),
            ('Bundle', 'attached if it fits well'),
            ('Gap', 'flagged when library is'),
            ('', 'thin, mentor can fill it'),
            ('Next likely', 'what usually follows')]),
    ]
    cw, top, ch = 224, 104, 420
    for ci, (x, head, hi, rows) in enumerate(cols):
        out.append(card(x, top, cw, ch, t, stroke=t['accent'] if hi else t['grid']))
        out.append(text(x + 18, top + 36, head, 18, t['accent'] if hi else t['ink'], 700))
        y = top + 74
        for name, what in rows:
            if name:
                y += 12
                out.append(text(x + 18, y, name, 15, t['ink'], 600))
                y += 21
            out.append(text(x + 18, y, what, 13, t['ink2']))
            y += 22
        if ci < 3:
            out.append(arrow(x + cw + 1, top + ch / 2, x + cw + 15, top + ch / 2, t['accent']))
    # Feedback loop along the bottom, from the output back to the first column.
    ly = top + ch + 44
    out.append('<path d="M%d %d V%d H%d V%d" fill="none" stroke="%s" stroke-width="2" stroke-dasharray="6 5"/>'
               % (860, top + ch + 2, ly, 140, top + ch + 10, t['accent']))
    out.append('<path d="M140 %d l-5 9 h10 z" fill="%s"/>' % (top + ch + 1, t['accent']))
    out.append('<rect x="%d" y="%d" width="660" height="26" fill="%s"/>' % (170, ly - 13, t['bg']))
    out.append(text(500, ly + 5, 'Feedback, test runs and commits update the model and your taste, kept in ~/.sfp', 15, t['accent'], 600, 'middle'))
    return svg(w, h, title, sub + ' Reads the task, project, phase, history and feedback; signals vote; quorum, rerank, cards, taste and roles choose; it hands over ordered skills, a bundle, a gap and what is likely next.',
               ''.join(out), t)


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


def rounds(dz, t):
    rows = [('SFP picks the skills', dz['sfp']['rounds'], True, '%d of %d pages accepted' % (dz['sfp']['shipped'], dz['sfp']['n'])),
            ('No skills', dz['baseline']['rounds'], False, '%d of %d accepted' % (dz['baseline']['shipped'], dz['baseline']['n'])),
            ('Hand-picked design skills', dz['picked']['rounds'], False, '%d of %d accepted' % (dz['picked']['shipped'], dz['picked']['n']))]
    n = sum(v['n'] for v in dz.values())
    return bars_chart('Fewer rounds of "make it better"', 'Rounds of review until a reviewer would ship the page. Lower is better.',
                      rows, 5, lambda v: '%.1f rounds' % v,
                      ['%d blind runs across 3 design tasks. The reviewer did not know which setup made each page.' % n,
                       'A page never accepted counts as 5 rounds.'], t)


def write(folder, name, body):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)


def result_charts(data):
    """The charts drawn from one benchmark run (bench/run_all.py calls this with its results)."""
    for mode, t in THEMES.items():
        write(CHARTS, 'headline-%s.svg' % mode, headline(data['results'], t))
        write(CHARTS, 'plain-words-%s.svg' % mode, plain_words(data['results'], t))
        write(CHARTS, 'taste-%s.svg' % mode, taste(data, t))
        write(CHARTS, 'tokens-%s.svg' % mode, tokens(data, t))
        write(CHARTS, 'latency-%s.svg' % mode, latency(data['results'], t))


def main():
    latest = sorted(glob.glob(os.path.join(ROOT, 'bench', 'results', '*.json')))[-1]
    with open(latest, encoding='utf-8') as f:
        result_charts(json.load(f))
    with open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8') as f:
        total = len(json.load(f)['skills'])
    dz = design_numbers()
    for mode, t in THEMES.items():
        write(ASSETS, 'how-it-works-%s.svg' % mode, flow(total, t))
        write(ASSETS, 'hive-architecture-%s.svg' % mode, architecture(t))
        write(ASSETS, 'results-rounds-%s.svg' % mode, rounds(dz, t))
    print('wrote assets/{how-it-works,hive-architecture,results-rounds}-*.svg and bench/charts/* from', os.path.basename(latest))


if __name__ == '__main__':
    main()
