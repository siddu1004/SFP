#!/usr/bin/env python3
"""Does SFP make a coding agent's work better? Run each task with and without SFP's skills and grade the result.

  python3 bench/agent/run.py [--reps 2] [--model sonnet] [--only rate_limit,...] [--out DIR]

The agent is Claude Code in headless mode, isolated from everything installed on the machine (no plugins, skills,
slash commands, MCP servers, hooks or user settings), so both arms are the same agent with the same tools. The only
difference: in the SFP arm the workspace holds the rule file the SFP Hive extension writes for the task (as
CLAUDE.md), naming the skills the hive chose and the SKILL.md file to read for each. Grading never shows the agent
the hidden checks. See docs/AGENT-BENCH.md.
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
TASKS = os.path.join(HERE, 'tasks')
STRIP_ENV = ('CLAUDE_CODE_SYNC_PLUGINS', 'CLAUDE_CODE_SYNC_SKILLS', 'CLAUDE_CODE_REMOTE', 'CLAUDE_CODE_SESSION_ID',
             'CLAUDE_CODE_REMOTE_SESSION_ID', 'CLAUDECODE')


def sfp_rule(prompt, workspace):
    data = tempfile.mkdtemp(prefix='sfp-data-')
    env = dict(os.environ, SFP_DATA_DIR=data)
    sel = subprocess.run([sys.executable, os.path.join(ROOT, 'mcp', 'sfp_hive.py'), 'select', prompt, '--project', workspace,
                          '--json'], capture_output=True, text=True, env=env, check=True).stdout
    rule = subprocess.run(['node', os.path.join(HERE, 'rule.js'), ROOT], input=sel, capture_output=True, text=True,
                          check=True).stdout
    shutil.rmtree(data, ignore_errors=True)
    return json.loads(sel), rule


def run_agent(prompt, workspace, model, log):
    empty = os.path.join(workspace, '..', os.path.basename(workspace) + '-mcp.json')
    with open(empty, 'w') as f:
        f.write('{"mcpServers":{}}')
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
    cmd = ['claude', '-p', prompt, '--model', model, '--setting-sources', 'project', '--disable-slash-commands',
           '--strict-mcp-config', '--mcp-config', empty, '--add-dir', ROOT, '--permission-mode', 'bypassPermissions',
           '--output-format', 'stream-json', '--verbose']
    t0 = time.time()
    with open(log, 'w') as out:
        p = subprocess.run(cmd, cwd=workspace, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=900)
    secs = time.time() - t0
    cost, turns, reads = 0.0, 0, []
    with open(log) as f:
        for line in f:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get('type') == 'result':
                cost, turns = ev.get('total_cost_usd', 0.0), ev.get('num_turns', 0)
            if ev.get('type') == 'assistant':
                for c in ev.get('message', {}).get('content', []):
                    if c.get('type') == 'tool_use':
                        target = json.dumps(c.get('input', {}))
                        if 'SKILL.md' in target:
                            reads.append(re.findall(r'skills/[^"\\]*?/SKILL\.md|[\w.-]+/SKILL\.md', target)[:1])
    return {'exit': p.returncode, 'seconds': round(secs, 1), 'cost_usd': round(cost, 4), 'turns': turns,
            'skill_reads': sum(1 for r in reads if r)}


def pytest_counts(cwd, target):
    xml = os.path.join(cwd, '.junit.xml')
    subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', target, '--junitxml', xml],
                   cwd=cwd, capture_output=True, text=True, timeout=300)
    if not os.path.exists(xml):
        return 0, 0
    s = open(xml).read()
    m = re.search(r'tests="(\d+)"', s)
    total = int(m.group(1)) if m else 0
    bad = sum(int(x) for x in re.findall(r'(?:failures|errors)="(\d+)"', s)[:2])
    return total - bad, total


def grade(task, workspace):
    g = tempfile.mkdtemp(prefix='grade-')
    shutil.copytree(workspace, g, dirs_exist_ok=True)
    hidden = os.path.join(TASKS, task, 'hidden')
    if task == 'cart_tests':
        sys.path.insert(0, hidden)
        from mutants import MUTANTS
        sys.path.pop(0)
        tests = [f for f in os.listdir(g) if re.match(r'(test_.*|.*_test)\.py$', f)]
        if not tests:
            return {'score': 0.0, 'detail': 'no test file written'}
        ok, total = pytest_counts(g, '.')
        if total == 0 or ok < total:
            return {'score': 0.0, 'detail': 'own tests fail on the original (%d/%d)' % (ok, total)}
        original = open(os.path.join(g, 'cart.py')).read()
        killed = []
        for desc, old, new in MUTANTS:
            assert old in original, desc
            open(os.path.join(g, 'cart.py'), 'w').write(original.replace(old, new, 1))
            ok, total = pytest_counts(g, '.')
            if ok < total:
                killed.append(desc)
        open(os.path.join(g, 'cart.py'), 'w').write(original)
        return {'score': round(len(killed) / len(MUTANTS), 3), 'detail': '%d/%d mutants caught' % (len(killed), len(MUTANTS)),
                'missed': [d for d, _, _ in MUTANTS if d not in killed], 'own_tests': total}
    shutil.copy(os.path.join(hidden, 'test_hidden.py'), os.path.join(g, 'test_hidden_grader.py'))
    ok, total = pytest_counts(g, 'test_hidden_grader.py')
    return {'score': round(ok / total, 3) if total else 0.0, 'detail': '%d/%d hidden checks' % (ok, total)}


def one(task, arm, rep, model, out):
    name = '%s-%s-%d' % (task, arm, rep)
    ws = os.path.join(out, 'work', name)
    shutil.rmtree(ws, ignore_errors=True)
    shutil.copytree(os.path.join(TASKS, task, 'repo'), ws)
    prompt = open(os.path.join(TASKS, task, 'prompt.txt')).read().strip()
    rec = {'task': task, 'arm': arm, 'rep': rep, 'model': model}
    if arm == 'sfp':
        sel, rule = sfp_rule(prompt, ws)
        with open(os.path.join(ws, 'CLAUDE.md'), 'w') as f:
            f.write(rule)
        rec['skills'] = [s['name'] for s in sel.get('stack', [])]
        rec['bundle'] = (sel.get('bundle') or {}).get('name')
    rec.update(run_agent(prompt, ws, model, os.path.join(out, 'logs', name + '.jsonl')))
    rec.update(grade(task, ws))
    print(json.dumps(rec), flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--model', default='sonnet')
    ap.add_argument('--only', default='')
    ap.add_argument('--arms', default='baseline,sfp')
    ap.add_argument('--out', default=os.path.join(tempfile.gettempdir(), 'sfp-agent-bench'))
    ap.add_argument('--jobs', type=int, default=5)
    a = ap.parse_args()
    tasks = a.only.split(',') if a.only else sorted(os.listdir(TASKS))
    os.makedirs(os.path.join(a.out, 'logs'), exist_ok=True)
    jobs = [(t, arm, r) for r in range(1, a.reps + 1) for t in tasks for arm in a.arms.split(',')]
    results = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for f in cf.as_completed([ex.submit(one, t, arm, r, a.model, a.out) for t, arm, r in jobs]):
            try:
                results.append(f.result())
            except Exception as e:  # one broken run must not lose the others
                print(json.dumps({'error': repr(e)}), flush=True)
    path = os.path.join(a.out, 'results.json')
    with open(path, 'w') as f:
        json.dump(results, f, indent=1)
    print('wrote ' + path)


if __name__ == '__main__':
    main()
