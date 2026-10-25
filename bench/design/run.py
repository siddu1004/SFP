#!/usr/bin/env python3
"""Design work over several rounds: how many rounds of review does the agent need before a page is good enough to ship?

  python3 bench/design/run.py [--reps 2] [--model sonnet] [--judge opus] [--rounds 4] [--arms baseline,sfp,picked]

Each run: the agent builds the page; it is screenshotted at desktop and phone width; a reviewer model scores the
screenshots against rubric.md without seeing the code, the rule file or which arm made it. If it would not ship, its
three requested changes go back to the agent as the next prompt, as a person would re-prompt, up to --rounds rounds.

Arms: baseline (no skills), sfp (the skills SFP chooses for the task, as the extension writes them), picked (two
design skills chosen by hand: impeccable and frontend-design). The agent is isolated as in bench/agent/run.py.
See docs/AGENT-BENCH.md.
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'bench', 'agent'))
import run as agent_bench  # noqa: E402  (isolation flags and the rule file)

PICKED = 'impeccable,frontend-design'
RUBRIC = open(os.path.join(HERE, 'rubric.md'), encoding='utf-8').read()


def rule_for(arm, prompt, ws):
    if arm == 'baseline':
        return None, []
    data = tempfile.mkdtemp(prefix='sfp-data-')
    cmd = [sys.executable, os.path.join(ROOT, 'mcp', 'sfp_hive.py'), 'select', prompt, '--project', ws, '--json']
    if arm == 'picked':
        cmd += ['--include', PICKED, '--max', '2', '--bundles', 'off', '--no-needs']
    sel = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, SFP_DATA_DIR=data), check=True).stdout
    rule = subprocess.run(['node', os.path.join(ROOT, 'bench', 'agent', 'rule.js'), ROOT], input=sel, capture_output=True,
                          text=True, check=True).stdout
    shutil.rmtree(data, ignore_errors=True)
    return rule, [s['name'] for s in json.loads(sel)['stack']]


def claude(prompt, cwd, model, log, resume=None, tools=None):
    empty = cwd.rstrip('/') + '-mcp.json'
    with open(empty, 'w') as f:
        f.write('{"mcpServers":{}}')
    env = {k: v for k, v in os.environ.items() if k not in agent_bench.STRIP_ENV}
    cmd = ['claude', '-p', prompt, '--model', model, '--setting-sources', 'project', '--disable-slash-commands',
           '--strict-mcp-config', '--mcp-config', empty, '--add-dir', ROOT, '--permission-mode', 'bypassPermissions',
           '--output-format', 'stream-json', '--verbose']
    if resume:
        cmd += ['--resume', resume]
    if tools:
        cmd += ['--tools', tools]
    with open(log, 'a') as out:
        subprocess.run(cmd, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=900)
    sid, cost, text = resume, 0.0, ''
    with open(log) as f:
        for line in f:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get('type') == 'result':
                sid, cost, text = ev.get('session_id', sid), ev.get('total_cost_usd', 0.0), ev.get('result', '')
    return sid, cost, text


def review(task, ws, judge, log):
    d = tempfile.mkdtemp(prefix='review-')
    subprocess.run(['node', os.path.join(HERE, 'shot.js'), ws], check=True, capture_output=True,
                   env=dict(os.environ, NODE_PATH=os.environ.get('NODE_PATH', '')))
    for n in ('desktop.png', 'mobile.png'):
        shutil.move(os.path.join(ws, n), os.path.join(d, n))
    prompt = RUBRIC + '\n\nThe request:\n' + task + '\n\nThe screenshots: desktop.png and mobile.png in this folder.'
    _, cost, text = claude(prompt, d, judge, log, tools='Read')
    m = re.search(r'\{.*\}', text, re.S)
    verdict = json.loads(m.group(0)) if m else {'overall': 0, 'ship': False, 'feedback': ['(no verdict)']}
    return verdict, cost, d


def one(task, arm, rep, a):
    name = '%s-%s-%d' % (task, arm, rep)
    ws = os.path.join(a.out, 'work', name)
    shutil.rmtree(ws, ignore_errors=True)
    os.makedirs(ws)
    prompt = open(os.path.join(HERE, 'tasks', task + '.txt')).read().strip()
    rule, skills = rule_for(arm, prompt, ws)
    if rule:
        with open(os.path.join(ws, 'CLAUDE.md'), 'w') as f:
            f.write(rule)
    log = os.path.join(a.out, 'logs', name + '.jsonl')
    jlog = os.path.join(a.out, 'logs', name + '-review.jsonl')
    rec = {'task': task, 'arm': arm, 'rep': rep, 'skills': skills, 'rounds': [], 'agent_cost': 0.0, 'review_cost': 0.0}
    sid, ask = None, prompt
    for r in range(1, a.rounds + 1):
        sid, cost, _ = claude(ask, ws, a.model, log, resume=sid)
        rec['agent_cost'] += cost
        if not os.path.exists(os.path.join(ws, 'index.html')):
            rec['rounds'].append({'round': r, 'overall': 0, 'ship': False, 'note': 'no index.html'})
            ask = 'There is no index.html yet. Please write the page as index.html.'
            continue
        verdict, jcost, shots = review(prompt, ws, a.judge, jlog)
        rec['review_cost'] += jcost
        keep = os.path.join(a.out, 'shots', '%s-r%d' % (name, r))
        shutil.copytree(shots, keep, dirs_exist_ok=True)
        shutil.copy(os.path.join(ws, 'index.html'), os.path.join(keep, 'index.html'))
        rec['rounds'].append(dict(verdict, round=r))
        if verdict.get('ship'):
            break
        ask = ('A design reviewer looked at screenshots of your page on desktop and on a phone, and asked for these '
               'changes:\n- ' + '\n- '.join(verdict.get('feedback', [])) + '\nPlease revise index.html.')
    shipped = [x['round'] for x in rec['rounds'] if x.get('ship')]
    rec['rounds_to_ship'] = shipped[0] if shipped else None
    rec['first_overall'] = rec['rounds'][0].get('overall', 0) if rec['rounds'] else 0
    rec['final_overall'] = rec['rounds'][-1].get('overall', 0) if rec['rounds'] else 0
    print(json.dumps({k: rec[k] for k in ('task', 'arm', 'rep', 'skills', 'rounds_to_ship', 'first_overall',
                                          'final_overall', 'agent_cost', 'review_cost')}), flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--model', default='sonnet')
    ap.add_argument('--judge', default='opus')
    ap.add_argument('--rounds', type=int, default=4)
    ap.add_argument('--arms', default='baseline,sfp,picked')
    ap.add_argument('--only', default='')
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--out', default=os.path.join(tempfile.gettempdir(), 'sfp-design-bench'))
    a = ap.parse_args()
    tasks = a.only.split(',') if a.only else sorted(f[:-4] for f in os.listdir(os.path.join(HERE, 'tasks')))
    for d in ('logs', 'shots', 'work'):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)
    jobs = [(t, arm, r) for r in range(1, a.reps + 1) for t in tasks for arm in a.arms.split(',')]
    results = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for f in cf.as_completed([ex.submit(one, t, arm, r, a) for t, arm, r in jobs]):
            try:
                results.append(f.result())
            except Exception as e:
                print(json.dumps({'error': repr(e)}), flush=True)
    with open(os.path.join(a.out, 'results.json'), 'w') as f:
        json.dump(results, f, indent=1)
    print('wrote ' + os.path.join(a.out, 'results.json'))


if __name__ == '__main__':
    main()
