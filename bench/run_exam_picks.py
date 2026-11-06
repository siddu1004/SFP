#!/usr/bin/env python3
"""bench/run_exam_picks.py - Generate pooled picks from Keyword, v3.19.0, and 3.20.0 for the exam."""
import json
import os
import sys
import tempfile
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

tmp = tempfile.mkdtemp(prefix='sfp-exam-')
os.environ['SFP_DATA_DIR'] = tmp
real_embed = os.path.join(os.path.expanduser('~/.sfp'), 'embeddings')
if os.path.isdir(real_embed):
    shutil.copytree(real_embed, os.path.join(tmp, 'embeddings'))

import sfp_mcp as core
import sfp_stack as v1
import sfp_hive as hive

exam_suites = [
    ('exam_plain', os.path.join(ROOT, 'tests', 'exam_plain.json')),
    ('exam_project', os.path.join(ROOT, 'tests', 'exam_project.json')),
    ('exam_reworded', os.path.join(ROOT, 'tests', 'exam_reworded.json')),
]

all_cases = []
for name, p in exam_suites:
    with open(p, encoding='utf-8') as f:
        d = json.load(f)
    cases = d if isinstance(d, list) else d.get('cases', [])
    for c in cases:
        all_cases.append({
            'suite': name,
            'task': c['task'],
            'project': c.get('project'),
            'expect': c.get('expect', []),
            'avoid': c.get('avoid', [])
        })

print(f"Total exam cases across 3 suites: {len(all_cases)}")

rows = []
hist = hive.History(v1.RECIPES, [])
old = v1.Markov(v1.RECIPES, [])

for i, c in enumerate(all_cases):
    task = c['task']
    proj = c['project']
    
    # 1. Keyword search (limit=3)
    kw_picks = [s['name'] for s in core.search(task, limit=3)]
    rows.append({'engine': 'keyword', 'task': task, 'picks': kw_picks})
    
    # 2. v3.19.0 / v1 recommender
    v1_res = v1.recommend(task, proj, chain=old)
    v1_picks = [x['name'] for x in v1_res.get('stack', [])]
    rows.append({'engine': 'v3.19.0', 'task': task, 'picks': v1_picks})
    
    # 3. SFP 3.20.0 (current engine)
    h_res = hive.select(task, proj, history=hist, semantic=True)
    h_picks = [x['name'] for x in h_res.get('stack', [])]
    lead = h_res.get('lead')
    if lead and lead in h_picks:
        h_picks = [lead] + [x for x in h_picks if x != lead]
    rows.append({'engine': '3.20.0', 'task': task, 'picks': h_picks})

out_path = os.path.join(ROOT, 'bench', 'exam_picks.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(rows, f, indent=1)

print(f"Saved {len(rows)} pick records to {out_path}")
shutil.rmtree(tmp, ignore_errors=True)
