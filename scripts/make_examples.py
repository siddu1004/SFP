#!/usr/bin/env python3
"""Write what people say when they have the problem a skill solves but do not know it exists, with a local model.

Meaning search finds a skill by these requests as well as its description, so they should sound like a beginner with a symptom,
not like the skill. Resumable: finished skills are kept. Writes to the given file, so it can be compared before replacing
skill_examples.json.

  python3 scripts/make_examples.py [out.json] [model] [limit]
"""
import json
import os
import re
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('SFP_DATA_DIR', tempfile.mkdtemp(prefix='sfp-examples-'))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))
import sfp_mcp as core  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'skill_examples.beginner.json')
MODEL = sys.argv[2] if len(sys.argv) > 2 else 'lfm2-24b-a2b'
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9
URL = 'http://127.0.0.1:1234/v1/chat/completions'
BATCH = 5
PER_SKILL = 8
PROMPT = ('For each guide below, write %d different things a developer might say to their AI assistant when they have the problem this '
          'guide solves but do not know the guide exists. Use plain everyday words. Describe symptoms and goals, not solutions. Some vague, '
          'some annoyed, some short. Never use a word from the guide\'s name. Each one 5 to 25 words.\n\n%s\n\n'
          'Answer as JSON only: {"<guide name>": ["...", ...], ...}')


def ask(prompt):
    body = {'model': MODEL, 'temperature': 0.7, 'max_tokens': 2400, 'messages': [{'role': 'user', 'content': prompt}]}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as r:
        text = json.load(r)['choices'][0]['message'].get('content') or ''
    text = re.sub(r'<think>.*?</think>', ' ', text, flags=re.S)
    return json.loads(text[text.index('{'):text.rindex('}') + 1])


def clean(name, requests):
    own = {w for w in name.lower().split('-') if len(w) > 2}
    out = []
    for q in requests if isinstance(requests, list) else []:
        if not isinstance(q, str):
            continue
        q = q.strip()
        words = set(re.findall(r'[a-z0-9]+', q.lower()))
        if 5 <= len(q.split()) <= 25 and not own & words and q not in out:
            out.append(q)
    return out[:PER_SKILL]


import concurrent.futures
import threading

LOCK = threading.Lock()


def process_chunk(chunk, out, i, total, t0):
    listing = '\n'.join('- %s: %s' % (s['name'], ' '.join((s['description'] or '').split())[:300]) for s in chunk)
    data = {}
    for _ in range(3):
        try:
            data = ask(PROMPT % (PER_SKILL, listing))
            break
        except (OSError, ValueError, KeyError, IndexError):
            time.sleep(2)
    with LOCK:
        for s in chunk:
            got = clean(s['name'], data.get(s['name'], []))
            if got:
                out[s['name']] = got
        tmp = OUT + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, sort_keys=True)
        os.replace(tmp, OUT)
        print('%d/%d done  %.0fs' % (len(out), total, time.time() - t0), flush=True)


def main():
    out = {}
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as f:
            out = json.load(f)
    todo = [s for s in core.CATALOG['skills'] if len(out.get(s['name'], [])) < 3][:LIMIT]
    total_skills = len(core.CATALOG['skills'])
    t0 = time.time()
    chunks = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(process_chunk, c, out, idx, total_skills, t0) for idx, c in enumerate(chunks)]
        concurrent.futures.wait(futures)


if __name__ == '__main__':
    main()
