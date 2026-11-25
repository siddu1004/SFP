#!/usr/bin/env python3
"""The one benchmark behind the README and its images: writes bench/results/release.json and bench/RESULTS.md.

  python3 bench/release.py            measure keyword search, SFP with no model, and SFP with an embedding model if one answers

A task counts as right when the chosen skills include one a person marked correct for it. "First" means the skill SFP puts
first. "Map" means the right skill is among the next best skills the agent is shown.

The plain and project sets named REGRESSION were never used to train or tune a weight, but their totals were looked at
after each change, so a brand new set may score a little lower. TUNED sets are reported apart. Nothing is written to ~/.sfp:
every engine runs in its own process with a temporary data folder.
"""
import datetime
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'bench', 'results', 'release.json')
PLAIN = ('plain_words_holdout2', 'search_reworded_holdout', 'final_heldout_plain', 'final_heldout_reworded')
PROJECT = ('hive_heldout', 'final_heldout_project')
TUNED = ('stack_eval',)
NOTHING = ('precision_heldout',)
GROUPS = (('plain', PLAIN), ('project', PROJECT), ('project_tuned', TUNED), ('nothing', NOTHING))
MAP_SIZES = (3, 10, 24, 40, 60)
ENGINES = ('keyword', 'words', 'meaning')
ASKS = ('make the login not get hacked', 'test all the buttons on my site', 'my page loads too slowly', 'turn my notes into a slide deck')


def wilson(k, n, z=1.96):
    if not n:
        return [0, 0]
    p = k / n
    mid, half, base = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)), 1 + z * z / n
    return [round(100 * (mid - half) / base), round(100 * (mid + half) / base)]


def load(hive, name, tmp):
    with open(os.path.join(ROOT, 'tests', name + '.json'), encoding='utf-8') as f:
        d = json.load(f)
    if isinstance(d, dict) and 'projects' in d:
        hive._projects(d, os.path.join(tmp, name))
        return [(c['task'], os.path.join(tmp, name, c['project']), c.get('expect') or []) for c in d['cases']]
    return [(c['task'], None, c.get('expect') or []) for c in (d if isinstance(d, list) else d['cases'])]


def run_engine(engine):
    """Score one engine in this process and print its result as JSON."""
    sys.path.insert(0, os.path.join(ROOT, 'mcp'))
    import sfp_city
    import sfp_embed
    import sfp_hive as hive
    import sfp_mcp as core
    tmp = tempfile.mkdtemp(prefix='sfp-release-')
    if engine != 'keyword':
        hive.select('warm the index and the model')
    sets, took, tokens, maps, map_tokens, n_map = {}, [], [], {k: 0 for k in MAP_SIZES}, [], 0
    for _, names in GROUPS:
        for name in names:
            row = {'n': 0, 'chosen': 0, 'first': 0, 'empty': 0, 'nothing_n': 0, 'nothing_empty': 0}
            for task, project, expect in load(hive, name, tmp):
                want = {x for x in expect if x in core.SKILLS}
                t0 = time.perf_counter()
                if engine == 'keyword':
                    picks = [s['name'] for s in core.search(task, limit=3)]
                else:
                    res = hive.select(task, project)
                    lead = res.get('lead')
                    picks = ([lead] if lead else []) + [s['name'] for s in res['stack'] if s['name'] != lead]
                    tokens.append(res['tokens'])
                    if res['city']:
                        map_tokens.append(len(sfp_city.format_map(res['city'])) / 4)
                took.append(time.perf_counter() - t0)
                if want:
                    row['n'] += 1
                    row['chosen'] += bool(want & set(picks))
                    row['first'] += bool(picks) and picks[0] in want
                    row['empty'] += not picks
                    if name in PLAIN and engine != 'keyword':
                        order = sfp_city.rank(task, sfp_embed.survey(task))[0]
                        n_map += 1
                        for k in MAP_SIZES:
                            maps[k] += bool(want & set(order[:k]))
                else:
                    row['nothing_n'] += 1
                    row['nothing_empty'] += not picks
            sets[name] = row
    groups = {}
    for g, names in GROUPS:
        a = {k: sum(sets[n][k] for n in names) for k in ('n', 'chosen', 'first', 'empty', 'nothing_n', 'nothing_empty')}
        pct = lambda k, n: round(100 * a[k] / a[n]) if a[n] else None
        groups[g] = {'n': a['n'], 'chosen': pct('chosen', 'n'), 'first': pct('first', 'n'), 'range': wilson(a['chosen'], a['n']),
                     'nothing_n': a['nothing_n'], 'nothing_empty': pct('nothing_empty', 'nothing_n')}
    took.sort()
    out = {'sets': sets, 'groups': groups, 'ms': {'typical': round(1000 * took[len(took) // 2], 1), 'slowest_5': round(1000 * took[int(len(took) * .95)], 1)}}
    if tokens:
        out['tokens'] = {'stack': round(sum(tokens) / len(tokens)), 'map': round(sum(map_tokens) / max(1, len(map_tokens)))}
        out['map'] = {'n': n_map, 'hold': {str(k): round(100 * v / max(1, n_map), 1) for k, v in maps.items()}}
    if engine != 'keyword':
        out['asks'] = []
        for a in ASKS:
            r = hive.select(a)
            out['asks'].append({'task': a, 'stack': [{'name': s['name'], 'category': s['category']} for s in r['stack']], 'lead': r['lead'],
                                'city': [{'tower': t['tower'], 'floors': [f['name'] for f in t['floors']]} for t in r['city']]})
        out['taste'] = taste(hive)
    print('RESULT ' + json.dumps(out))


def taste(hive):
    """Simulated learners (tests/taste_generalise.json): does the first pick have the wanted format and job, before and after?"""
    import sfp_cards
    import sfp_learn
    with open(os.path.join(ROOT, 'tests', 'taste_generalise.json'), encoding='utf-8') as f:
        people = json.load(f)['personas']
    out, keep = {}, os.environ['SFP_DATA_DIR']

    def right(case):
        res = hive.select(case['task'])
        card = sfp_cards.get_card(res['lead']) if res.get('lead') else {}
        return case['expect_form'] in card.get('output', []) and (not case.get('expect_job') or card.get('job') == case['expect_job'])
    for pid, p in people.items():
        os.environ['SFP_DATA_DIR'] = tempfile.mkdtemp(prefix='sfp-taste-')
        before = sum(right(c) for c in p['tasks'])
        for e in p['history']:
            sfp_learn.update_taste(e['skill'], 2.0)
        after = [right(c) for c in p['tasks']]
        named = [ok for ok, c in zip(after, p['tasks']) if c['expect_form'] != p['taste_focus']]
        n = len(p['tasks'])
        out[pid] = {'name': p['name'], 'n': n, 'before': round(100 * before / n), 'after': round(100 * sum(after) / n),
                    'named_n': len(named), 'named_right': sum(named)}
    os.environ['SFP_DATA_DIR'] = keep
    return out


def write_page(result):
    e = result['engines']
    shown = [(k, l) for k, l in (('keyword', 'Keyword search'), ('words', 'SFP, no model'), ('meaning', 'SFP + bge-m3')) if k in e]
    pct = lambda a, b: '%d%%' % round(100 * a / b) if b else '-'
    lines = ['# Results for SFP %s' % result['version'], '', 'Written by `python3 bench/release.py` on %s at commit `%s`. The README and every image use the same data'
             % (result['date'], result['commit']) + ' ([results/release.json](results/release.json)).', '',
             'A task counts as right when the chosen skills include one a person marked correct for it. Each cell shows **right skill chosen / right skill first**.', '',
             '## Every set', '', '| Set | Tasks | Kind | ' + ' | '.join(l for _, l in shown) + ' |', '|---|---:|---|' + '---:|' * len(shown)]
    kind = {'plain': 'regression', 'project': 'regression', 'project_tuned': 'tuned', 'nothing': 'regression'}
    for g, names in GROUPS:
        for n in names:
            row = e['words']['sets'][n]
            lines.append('| `%s` | %d | %s | %s |' % (n, row['n'], kind[g], ' | '.join('%s / %s' % (pct(e[k]['sets'][n]['chosen'], e[k]['sets'][n]['n']), pct(e[k]['sets'][n]['first'], e[k]['sets'][n]['n'])) for k, _ in shown)))
            if row['nothing_n']:
                lines.append('| `%s`, tasks that need no skill, left empty | %d | %s | %s |' % (n, row['nothing_n'], kind[g], ' | '.join(pct(e[k]['sets'][n]['nothing_empty'], e[k]['sets'][n]['nothing_n']) for k, _ in shown)))
    lines += ['', '**Regression** sets were never used to train or tune a weight, but their totals were looked at after each change, so a brand new set may score a little lower. **Tuned** sets were used.', '',
              '## How often the right skill is on the map', '', '| Best skills shown | ' + ' | '.join(l for k, l in shown if 'map' in e[k]) + ' |', '|---:|' + '---:|' * sum('map' in e[k] for k, _ in shown)]
    for k in MAP_SIZES:
        lines.append('| %d | %s |' % (k, ' | '.join('%.1f%%' % e[x]['map']['hold'][str(k)] for x, _ in shown if 'map' in e[x])))
    lines += ['', 'On the %d plain tasks. The agent is shown the best 40, grouped in towers, in about %d tokens.' % (e['words']['map']['n'], e['words']['tokens']['map']), '',
              '## Taste, simulated learners', '', '| Learner | Tasks | First pick in the liked format and the right job, before | after | Named formats followed |', '|---|---:|---:|---:|---:|']
    for p in (e.get('meaning') or e['words'])['taste'].values():
        lines.append('| %s | %d | %d%% | %d%% | %d of %d |' % (p['name'], p['n'], p['before'], p['after'], p['named_right'], p['named_n']))
    lines += ['', '## Time and tokens', '', '| | ' + ' | '.join(l for _, l in shown) + ' |', '|---|' + '---:|' * len(shown),
              '| Typical choice | %s |' % ' | '.join('%.0f ms' % e[k]['ms']['typical'] for k, _ in shown), '| Slowest 5% | ' + ' | '.join('%.0f ms' % e[k]['ms']['slowest_5'] for k, _ in shown) + ' |',
              '| Tokens loaded, average | %s |' % ' | '.join(('%d' % e[k]['tokens']['stack']) if 'tokens' in e[k] else '-' for k, _ in shown), '',
              'One laptop, models already loaded. Tokens are estimated at 4 characters each.', '',
              '## What was withdrawn', '',
              'Earlier pages reported two sets that do not test what they seemed to. On the "v2" sets plain keyword search scores 98%, because their tasks repeat the words of the skill they expect. '
              'On the "exam" a local model rated the picks and keyword search gets 93% under the same rating. Neither is used any more.', '']
    with open(os.path.join(ROOT, 'bench', 'RESULTS.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


def main():
    if len(sys.argv) > 2 and sys.argv[1] == '--engine':
        return run_engine(sys.argv[2])
    sys.path.insert(0, os.path.join(ROOT, 'mcp'))
    import sfp_hive
    commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    result = {'version': sfp_hive.VERSION, 'commit': commit, 'date': datetime.date.today().isoformat(), 'engines': {}}
    home = os.path.join(os.path.expanduser('~'), '.sfp', 'embeddings')
    for engine in ENGINES:
        data = tempfile.mkdtemp(prefix='sfp-release-data-')
        if engine == 'meaning':
            if not os.path.isdir(home):
                print('meaning: no embeddings (python3 mcp/sfp_embed.py build), left out')
                continue
            shutil.copytree(home, os.path.join(data, 'embeddings'))
        env = dict(os.environ, SFP_DATA_DIR=data, SFP_SEMANTIC='1' if engine == 'meaning' else '0', SFP_RESEARCH='0', PYTHONIOENCODING='utf-8')
        for k in ('SFP_RERANK', 'SFP_REWRITE', 'SFP_FUSED', 'SFP_NO_LEARNING', 'SFP_MAP'):
            env.pop(k, None)
        done = subprocess.run([sys.executable, os.path.abspath(__file__), '--engine', engine], cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
        line = [x for x in (done.stdout or '').splitlines() if x.startswith('RESULT ')]
        if not line:
            raise SystemExit('%s failed:\n%s' % (engine, (done.stderr or '')[-2000:]))
        result['engines'][engine] = json.loads(line[0][7:])
        g = result['engines'][engine]['groups']
        print('%-8s plain %s/%s  project %s/%s  nothing empty %s%%  %s' % (engine, g['plain']['chosen'], g['plain']['first'], g['project']['chosen'],
              g['project']['first'], g['nothing']['nothing_empty'], result['engines'][engine].get('map', {}).get('hold', '')), flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, indent=1)
        f.write('\n')
    write_page(result)
    print('written to %s and bench/RESULTS.md' % OUT)


if __name__ == '__main__':
    main()
