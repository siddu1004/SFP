#!/usr/bin/env python3
"""scripts/make_cards.py - generate skill_cards.json for every skill in catalog.json.

Each card:
{
  "job": explain | build | fix | test | review | design | deploy | research | write | plan | automate | data | secure | optimize | operate,
  "output": [text | code | diagram | animation | video | slides | interactive | audio | image | document | config | report],
  "style": step-by-step | visual | hands-on | reference | conversational | checklist,
  "depth": beginner | practitioner | expert,
  "needs": [tools/programs required, e.g. manim, ffmpeg, remotion, docker],
  "substitutes_for": kebab-case slug for the job alternative skills also do
}
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

JOBS = {'explain', 'build', 'fix', 'test', 'review', 'design', 'deploy', 'research', 'write', 'plan', 'automate', 'data', 'secure', 'optimize', 'operate'}
OUTPUTS = {'text', 'code', 'diagram', 'animation', 'video', 'slides', 'interactive', 'audio', 'image', 'document', 'config', 'report'}
STYLES = {'step-by-step', 'visual', 'hands-on', 'reference', 'conversational', 'checklist'}
DEPTHS = {'beginner', 'practitioner', 'expert'}

COMMON_TOOLS = {
    'manim', 'ffmpeg', 'remotion', 'docker', 'docker-compose', 'playwright', 'blender',
    'qiskit', 'pytest', 'jest', 'vitest', 'kubectl', 'terraform', 'git', 'ollama',
    'clickhouse', 'postgres', 'mysql', 'sqlite', 'redis', 'caddy', 'nginx', 'puppeteer',
    'imagemagick', 'pandoc', 'graphviz', 'screenpipe', 'strix', 'omniroute'
}

def skill_md_hash(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]

def card_from_words(name, desc, body):
    full = (name + ' ' + desc + ' ' + body[:2000]).lower()
    meta = (name.replace('-', ' ') + ' ' + desc).lower()
    name_parts = set(name.lower().split('-'))
    desc_low = desc.lower()
    
    # Needs detection
    needs = []
    for tool in COMMON_TOOLS:
        if re.search(r'\b' + re.escape(tool) + r'\b', full):
            needs.append(tool)
            
    # Output forms (derived from skill name and description first to avoid body noise)
    outs = []
    if any(w in meta for w in ('animation', 'manim', 'animate', 'lottie', 'motion-graphic', 'animated', 'gif')):
        outs.append('animation')
    if any(w in meta for w in ('video', 'remotion', 'mp4', 'screen recording', 'screencast', 'videodb', 'walkthrough video')):
        outs.append('video')
    if any(w in meta for w in ('slides', 'slide deck', 'presentation', 'pitch deck', 'wowerpoint')):
        outs.append('slides')
    if any(w in meta for w in ('diagram', 'mermaid', 'chart', 'flowchart', 'architecture diagram', 'wireframe')):
        outs.append('diagram')
    if any(w in meta for w in ('interactive', 'simulator', 'playground', 'canvas', 'repl')):
        outs.append('interactive')
    if any(re.search(r'\b' + re.escape(w) + r'\b', meta) for w in ('image', 'images', 'svg', 'icon', 'icons', 'graphic', 'logo', 'screenshot', 'screenshots', 'gif')):
        outs.append('image')
    if any(w in meta for w in ('config', 'configuration', 'dockerfile', 'yaml', 'k8s manifest', 'helm chart')):
        outs.append('config')
    if any(w in meta for w in ('report', 'audit report', 'findings', 'scorecard', 'metrics log', 'summary report')):
        outs.append('report')
    if any(re.search(r'\b' + re.escape(w) + r'\b', meta) for w in ('document', 'documents', 'spec', 'documentation', 'docs', 'markdown', 'rfc', 'adr', 'changelog', 'release notes', 'digest', 'standup', 'article', 'blog')):
        outs.append('document')
    if not any(o in outs for o in ('animation', 'video', 'slides', 'diagram', 'image')) and any(re.search(r'\b' + re.escape(w) + r'\b', meta) for w in ('code', 'coding', 'implementation', 'script', 'function', 'test', 'tests', 'testing', 'patterns', 'boilerplate', 'library', 'framework', 'api', 'backend', 'frontend', 'concurrency', 'database', 'queries', 'schema', 'actor', 'persistence', 'swift', 'rust', 'golang', 'python', 'kotlin', 'java', 'cpp', 'middleware', 'token', 'jwt', 'cache', 'tree')):
        outs.append('code')
    if not outs or ('document' in outs and 'write' in name_parts) or (('animation' not in outs and 'video' not in outs and 'slides' not in outs) and any(w in meta for w in ('explanation', 'explain', 'teach', 'lesson', 'guideline', 'guidelines', 'guide', 'advice', 'principles', 'lookup', 'reference', 'article', 'writing', 'summary', 'docs', 'documentation'))):
        outs.append('text')
    # Filter to allowed
    outs = [o for o in outs if o in OUTPUTS]
    if not outs:
        outs = ['code' if any(w in full for w in ('code', 'pattern', 'test', 'build')) else 'text']

    # Job detection (using token matching on name_parts to avoid substring collisions like 'fast' in 'fastapi' or 'ui' in 'build')
    if any(w in name_parts for w in ('teach', 'explain', 'concept', 'tutorial')) or name in ('manim-video', 'documentation-lookup') or any(w in desc_low for w in ('animated explainer', 'manim explainers', 'teach adaptively')):
        job = 'explain'
    elif (any(w in name_parts for w in ('secure', 'security', 'ciso', 'vulnerability', 'vulnerabilities', 'penetration', 'pentest', 'pentesting', 'owasp', 'hardening')) or any(w in desc_low for w in ('penetration testing', 'security vulnerabilities', 'owasp top 10', 'security checklist', 'security hardening', 'escape attempts', 'container escape'))) and 'review' not in name_parts:
        job = 'secure'
    elif any(w in name_parts for w in ('optimize', 'perf', 'performance', 'latency', 'compress', 'compression', 'speed', 'accelerator')) or any(w in desc_low for w in ('performance tuning', 'optimize query', 'speed up', 'profiling', 'frame budget', 'dropped frames')):
        job = 'optimize'
    elif any(w in name_parts for w in ('test', 'tests', 'tdd', 'testing', 'benchmark')) or any(w in desc_low for w in ('unit test', 'integration test', 'e2e test', 'test-driven', 'property-based test')):
        job = 'test'
    elif any(w in name_parts for w in ('fix', 'defect', 'debug', 'debugging', 'repair', 'patch')) or any(w in desc_low for w in ('fix bug', 'troubleshoot', 'regression test', 'diagnose bug', 'root cause')):
        job = 'fix'
    elif any(w in name_parts for w in ('review', 'lint', 'inspector', 'quality')) or name in ('code-quality', 'quality-scan', 'caveman-evidence-review', 'gsd-code-review') or any(w in desc_low for w in ('code review', 'linting', 'quality scan', 'audit for')):
        job = 'review'
    elif any(w in name_parts for w in ('video', 'remotion', 'screencast')) or name in ('ui-demo', 'remotion-video-creation', 'moneyprinterturbo-video', 'tasteforge-video'):
        job = 'build'
    elif any(w in name_parts for w in ('design', 'ui', 'ux', 'css', 'style', 'taste', 'theme', 'component', 'animation', 'animate', 'motion', 'layout', 'slides', 'wowerpoint', 'gif')) or any(w in desc_low for w in ('slide deck', 'animated gif', 'ui polish', 'visual design')):
        job = 'design'
    elif any(w in name_parts for w in ('deploy', 'deployment', 'docker', 'k8s', 'kubernetes', 'release', 'tunnel', 'bump', 'ci', 'cd')) or any(w in desc_low for w in ('release workflow', 'git tagging', 'github releases', 'semantic versioning')):
        job = 'deploy'
    elif any(w in name_parts for w in ('research', 'paper', 'literature', 'pubmed', 'clinical', 'search', 'explore', 'study')):
        job = 'research'
    elif any(w in name_parts for w in ('write', 'writing', 'docs', 'copy', 'article', 'changelog', 'authoring', 'translate', 'i18n')):
        job = 'write'
    elif any(w in name_parts for w in ('plan', 'planning', 'roadmap', 'decision', 'decisions', 'journey', 'requirements', 'milestone', 'council')):
        job = 'plan'
    elif any(w in name_parts for w in ('automate', 'automation', 'crawl', 'scraper', 'workflow', 'workflows', 'n8n', 'bot')):
        job = 'automate'
    elif any(w in name_parts for w in ('data', 'sql', 'clickhouse', 'db', 'migration', 'migrations', 'database', 'query')) and 'patterns' not in name_parts:
        job = 'data'
    elif any(w in name_parts for w in ('ops', 'operate', 'monitor', 'health', 'sysadmin', 'network', 'status', 'backup', 'backups')):
        job = 'operate'
    else:
        job = 'build'

    # Style
    if 'animation' in outs or 'video' in outs or 'diagram' in outs or 'image' in outs or 'visual' in meta:
        style = 'visual'
    elif job in ('test', 'build', 'fix') or 'hands-on' in meta or 'code' in outs:
        style = 'hands-on'
    elif job == 'review' or 'checklist' in meta:
        style = 'checklist'
    elif job == 'explain' or 'reference' in meta or 'api' in name_parts:
        style = 'reference'
    elif 'conversational' in meta:
        style = 'conversational'
    else:
        style = 'step-by-step'

    # Depth
    if any(w in meta for w in ('expert', 'internals', 'advanced', 'hardened', 'kernel', 'low-level', 'security architecture')):
        depth = 'expert'
    elif any(w in meta for w in ('beginner', 'intro', 'tutorial', 'fundamentals', 'basics')):
        depth = 'beginner'
    else:
        depth = 'practitioner'

    # Substitutes_for: domain/job grouping
    if job == 'explain' or name in ('manim-video', 'teach-me', 'documentation-lookup'):
        sub = 'explain-concepts'
        job = 'explain'
    elif 'video' in outs or any(w in name_parts for w in ('video', 'remotion', 'screencast')) or name == 'ui-demo':
        sub = 'video-creation'
    elif 'animation' in outs or any(w in name_parts for w in ('anim', 'animation', 'animate', 'motion')):
        sub = 'motion-and-animation'
    elif job == 'test':
        if 'e2e' in full or 'playwright' in full:
            sub = 'e2e-testing'
        elif 'tdd' in full:
            sub = 'test-driven-development'
        else:
            sub = 'unit-testing'
    elif job == 'review':
        if 'security' in full:
            sub = 'security-review'
        else:
            sub = 'code-review'
    elif job == 'design':
        if 'system' in full or 'pattern' in full:
            sub = 'design-systems'
        else:
            sub = 'ui-ux-design'
    elif job == 'deploy':
        sub = 'deployment-and-containers'
    elif job == 'research':
        sub = 'literature-and-search'
    elif job == 'write':
        sub = 'technical-writing-and-docs'
    elif job == 'plan':
        sub = 'architecture-and-planning'
    elif job == 'automate':
        sub = 'workflow-automation'
    elif job == 'data':
        sub = 'database-and-migrations'
    elif job == 'secure':
        sub = 'application-security'
    elif job == 'optimize':
        sub = 'performance-optimization'
    elif job == 'operate':
        sub = 'infrastructure-and-ops'
    else:
        sub = 'software-engineering-patterns'

    return {
        'job': job,
        'output': outs,
        'style': style,
        'depth': depth,
        'needs': sorted(set(needs)),
        'substitutes_for': sub,
        'source': 'words'
    }

def validate_card(c):
    if not isinstance(c, dict):
        return False
    if c.get('job') not in JOBS:
        return False
    outs = c.get('output')
    if not isinstance(outs, list) or not outs or not all(o in OUTPUTS for o in outs):
        return False
    if c.get('style') not in STYLES:
        return False
    if c.get('depth') not in DEPTHS:
        return False
    if not isinstance(c.get('needs'), list):
        return False
    if not c.get('substitutes_for') or not isinstance(c.get('substitutes_for'), str):
        return False
    return True

def ask_batch_model(batch, ep):
    """batch is list of (name, desc, excerpt)"""
    items = []
    for name, desc, excerpt in batch:
        items.append(f"Skill: {name}\nDescription: {desc}\nExcerpt:\n{excerpt[:600]}")
    
    prompt = f"""For each skill, determine its card properties in strict JSON.
Allowed jobs: [explain, build, fix, test, review, design, deploy, research, write, plan, automate, data, secure, optimize, operate]
Allowed outputs: subset of [text, code, diagram, animation, video, slides, interactive, audio, image, document, config, report]
Allowed styles: [step-by-step, visual, hands-on, reference, conversational, checklist]
Allowed depth: beginner | practitioner | expert
needs: list of required external CLI tools (e.g. ["docker", "ffmpeg"], [] if none)
substitutes_for: slug for the capability alternative skills also do (e.g. "explain-concepts", "unit-testing", "code-review", "ui-ux-design", "database-and-migrations")

Skills:
""" + "\n---\n".join(items) + """

Respond with ONLY a JSON array of cards matching:
[{"name": "<name>", "job": "...", "output": ["..."], "style": "...", "depth": "...", "needs": [], "substitutes_for": "..."}, ...]"""

    body = {'model': ep['model'], 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 1200, 'temperature': 0.1}
    req = urllib.request.Request(ep['base_url'] + '/chat/completions', json.dumps(body).encode(),
                                 {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30.0) as r:
        resp = json.loads(r.read().decode('utf-8'))
    content = resp['choices'][0]['message'].get('content', '')
    content = re.sub(r'<think>.*?</think>', ' ', content, flags=re.S)
    m = re.search(r'\[\s*\{.*\}\s*\]', content, re.S)
    if not m:
        return None
    cards = json.loads(m.group(0))
    if not isinstance(cards, list):
        return None
    return {c.get('name'): c for c in cards if isinstance(c, dict) and c.get('name')}

def make_cards(catalog_path=None, output_path=None, use_model=True):
    catalog_path = catalog_path or os.path.join(ROOT, 'catalog.json')
    output_path = output_path or os.path.join(ROOT, 'skill_cards.json')
    
    with open(catalog_path, encoding='utf-8') as f:
        catalog = json.load(f)
    
    existing = {}
    if os.path.isfile(output_path):
        try:
            with open(output_path, encoding='utf-8') as f:
                data = json.load(f)
                existing = data.get('cards', {})
        except Exception:
            existing = {}

    skills = catalog.get('skills', [])
    print(f"Total skills to card: {len(skills)}")

    # Check which endpoints are available
    ep = None
    if use_model:
        # Check local models (1234 or 11434)
        for url, mname in [('http://127.0.0.1:1234/v1', 'lfm2-24b-a2b'), ('http://127.0.0.1:11434/v1', 'llama3')]:
            try:
                test_req = urllib.request.Request(url + '/models', headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(test_req, timeout=1.5) as r:
                    ep = {'base_url': url, 'model': mname}
                    print(f"Using model endpoint: {url} ({mname})")
                    break
            except Exception:
                continue

    out_cards = dict(existing)
    to_card = []

    for s in skills:
        name = s['name']
        desc = s.get('description', '')
        rel_path = s['path']
        full_path = os.path.join(ROOT, rel_path, 'SKILL.md')
        text = ''
        if os.path.isfile(full_path):
            with open(full_path, encoding='utf-8', errors='ignore') as f:
                text = f.read()
        h = skill_md_hash(text)
        
        # Check if existing card is valid and fresh
        card = out_cards.get(name)
        if card and card.get('hash') == h and validate_card(card):
            continue
            
        first_60 = '\n'.join(text.splitlines()[:60])
        to_card.append((name, desc, first_60, h, text))

    print(f"Skills needing cards: {len(to_card)}")

    # Process in batches of 5 with model if available
    batch_size = 5
    for i in range(0, len(to_card), batch_size):
        batch = to_card[i:i + batch_size]
        model_results = {}
        if ep:
            try:
                model_results = ask_batch_model([(n, d, ex) for n, d, ex, h, t in batch], ep) or {}
            except Exception as e:
                # Re-ask once
                try:
                    time.sleep(0.5)
                    model_results = ask_batch_model([(n, d, ex) for n, d, ex, h, t in batch], ep) or {}
                except Exception:
                    model_results = {}

        for n, d, ex, h, full_text in batch:
            m_card = model_results.get(n) if model_results else None
            if m_card and validate_card(m_card):
                out_cards[n] = {
                    'hash': h,
                    'job': m_card['job'],
                    'output': [o for o in m_card['output'] if o in OUTPUTS],
                    'style': m_card['style'],
                    'depth': m_card['depth'],
                    'needs': [w for w in m_card.get('needs', []) if isinstance(w, str)],
                    'substitutes_for': m_card['substitutes_for'],
                    'source': 'model'
                }
            else:
                w_card = card_from_words(n, d, full_text)
                w_card['hash'] = h
                out_cards[n] = w_card

        if (i // batch_size) % 10 == 0 or i + batch_size >= len(to_card):
            # Save progress
            with open(output_path + '.tmp', 'w', encoding='utf-8') as f:
                json.dump({'_version': 1, 'cards': out_cards}, f, indent=2)
            os.replace(output_path + '.tmp', output_path)
            print(f"Progress: {min(i + batch_size, len(to_card))}/{len(to_card)} cards processed.")

    print(f"Cards complete: {len(out_cards)} skills carded in {output_path}")
    return out_cards

if __name__ == '__main__':
    make_cards()
