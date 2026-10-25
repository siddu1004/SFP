#!/usr/bin/env python3
"""Convert any Git repository into an SFP agent skill with its own category.

Usage:
  python3 scripts/repo_to_skill.py <repo-url-or-path> [--category <cat>] [--name <name>] [--dest <path>] [--json]

Standard library only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATEGORIES_FILE = os.path.join(ROOT, 'categories.json')
TEMPLATES_DIR = os.path.join(ROOT, 'templates')

CATEGORY_KEYWORDS = {
    'frontend': ['react', 'vue', 'svelte', 'css', 'html', 'tailwind', 'nextjs', 'vite', 'ui', 'component', 'animation', 'dom'],
    'backend': ['django', 'fastapi', 'flask', 'express', 'spring', 'rails', 'nestjs', 'postgres', 'sql', 'orm', 'database', 'sqlite', 'mongodb'],
    'devops': ['docker', 'kubernetes', 'k8s', 'terraform', 'ci/cd', 'github actions', 'deploy', 'nginx', 'helm', 'ansible'],
    'security': ['pentest', 'vulnerability', 'auth', 'oauth', 'jwt', 'owasp', 'cipher', 'crypto', 'security', 'exploit', 'audit'],
    'ai-ml': ['pytorch', 'tensorflow', 'llm', 'transformer', 'huggingface', 'model', 'rag', 'embedding', 'agent', 'neural', 'inference'],
    'mobile': ['android', 'ios', 'flutter', 'react native', 'swift', 'kotlin', 'mobile'],
    'data-apis': ['api', 'scraper', 'crawler', 'rest', 'graphql', 'dataset', 'http', 'client'],
    'languages': ['golang', 'rust', 'python', 'typescript', 'cpp', 'csharp', 'compiler', 'parser', 'syntax'],
    'testing-quality': ['test', 'pytest', 'jest', 'mock', 'tdd', 'e2e', 'cypress', 'playwright', 'benchmark', 'assert'],
}


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\-]+', '-', text)
    return text.strip('-')


def clone_or_read(source):
    """(path, is_temporary) for a remote git URL or local directory."""
    if os.path.isdir(source):
        return os.path.abspath(source), False

    tmp_dir = tempfile.mkdtemp(prefix='sfp_repo_')
    url = source
    if not (url.startswith('http://') or url.startswith('https://') or url.startswith('git@')):
        url = f'https://github.com/{source}.git'

    res = subprocess.run(['git', 'clone', '--depth', '1', url, tmp_dir], capture_output=True, text=True)
    if res.returncode != 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f'Failed to clone {url}: {res.stderr.strip()}')
    return tmp_dir, True


def extract_context(repo_dir, max_chars=6000):
    """Extract README, manifest, and file listings."""
    readme_text = ''
    for name in ['README.md', 'README.rst', 'README.txt', 'readme.md']:
        p = os.path.join(repo_dir, name)
        if os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as f:
                    readme_text = f.read()
                    break
            except OSError:
                pass

    manifest = ''
    for m in ['package.json', 'pyproject.toml', 'Cargo.toml', 'go.mod', 'setup.py']:
        p = os.path.join(repo_dir, m)
        if os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as f:
                    manifest = f'Manifest ({m}):\n' + f.read(1200)
                    break
            except OSError:
                pass

    files_list = []
    for root, dirs, files in os.walk(repo_dir):
        if '.git' in dirs:
            dirs.remove('.git')
        rel = os.path.relpath(root, repo_dir)
        for fl in files[:10]:
            files_list.append(os.path.join(rel, fl))
        if len(files_list) > 25:
            break

    context = (
        'Repository Structure:\n' + '\n'.join(files_list[:20]) + '\n\n'
        + (manifest + '\n\n' if manifest else '')
        + 'README excerpt:\n' + readme_text[:max_chars]
    )
    return context, readme_text


def infer_category(name, context, custom=None):
    if custom:
        return custom
    text = (name + ' ' + context).lower()
    scores = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        hit = sum(1 for kw in kws if kw in text)
        if hit > 0:
            scores[cat] = hit
    if scores:
        return max(scores, key=scores.get)
    return 'engineering'


def query_local_llm(prompt, timeout=15):
    """Attempts to distill using a running local LLM (e.g. LM Studio on 1234 or Ollama on 11434)."""
    endpoints = [
        ('http://127.0.0.1:1234/v1/chat/completions', 'http://127.0.0.1:1234/v1/models'),
        ('http://127.0.0.1:11434/v1/chat/completions', 'http://127.0.0.1:11434/v1/models'),
    ]
    for chat_url, models_url in endpoints:
        try:
            req_m = urllib.request.Request(models_url)
            with urllib.request.urlopen(req_m, timeout=1.0) as resp:
                data = json.loads(resp.read().decode())
                m_list = [m['id'] for m in data.get('data', [])]
                if not m_list:
                    continue
                model_id = m_list[0]

            payload = {
                'model': model_id,
                'messages': [
                    {'role': 'system', 'content': 'You generate structured SFP agent skills in markdown with YAML frontmatter. Output only markdown.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2,
                'max_tokens': 2048
            }
            req_c = urllib.request.Request(chat_url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req_c, timeout=timeout) as resp:
                res = json.loads(resp.read().decode())
                content = res['choices'][0]['message']['content'].strip()
                if content.startswith('```markdown'):
                    content = content[11:]
                elif content.startswith('```'):
                    content = content[3:]
                if content.endswith('```'):
                    content = content[:-3]
                content = content.strip()
                if content.startswith('---'):
                    return content
        except Exception:
            continue
    return None


def distill_markdown(skill_name, category, context, readme):
    """Produces the SKILL.md content."""
    prompt = f"""Convert this git repository into an agent skill for SFP:
Skill Name: {skill_name}
Category: {category}

{context[:4500]}

Format requirement:
---
name: {skill_name}
description: "1-2 sentence trigger description with 'Use when...'"
---

# {skill_name}

## When to Use
- Specific task 1
- Specific task 2

## Core Concepts & Quickstart
(Essential commands, CLI syntax, or setup steps)

## Patterns & Code Recipes
(2-3 high-value, realistic code snippets or workflows)

## Common Pitfalls & Rules
(What NOT to do, gotchas, anti-patterns)
"""
    llm_out = query_local_llm(prompt)
    if llm_out:
        return llm_out

    # Fallback: extract title and description from README
    lines = [l.strip() for l in readme.splitlines() if l.strip()]
    desc = f"Workflows and patterns for {skill_name}. Use when building, configuring, or debugging with {skill_name}."
    for l in lines[1:5]:
        if not l.startswith('#') and len(l) > 20:
            clean_l = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', l)
            desc = f"{clean_l[:120].rstrip('.')} — use when developing or integrating {skill_name}."
            break

    return f"""---
name: {skill_name}
description: "{desc}"
---

# {skill_name}

Guidance, patterns, and procedural recipes for `{skill_name}`.

## When to Use
- Implementing or refactoring features using `{skill_name}`.
- Setting up configuration, CLI workflows, or dependencies.
- Diagnosing errors and verifying conventions for `{skill_name}`.

## Core Concepts & Quickstart
Follow the repository's standard installation and configuration patterns:
```bash
# Standard setup
git clone https://github.com/.../{skill_name}
```

## Best Practices & Patterns
1. Keep component boundaries clean and follow idioms established in the codebase.
2. Handle error states and edge cases explicitly.
3. Validate inputs and conform to standard schema constraints.

## Common Pitfalls
- Avoid hardcoding environment-dependent configuration.
- Check return codes and handle network or resource timeouts.
"""


def register_skill_in_categories(skill_name, category, category_desc=None, categories_file=CATEGORIES_FILE):
    """Assigns the skill to its category in categories.json, creating the category if needed."""
    if not os.path.isfile(categories_file):
        return

    with open(categories_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. Register new category if absent
    if category not in data.get('categories', {}):
        desc = category_desc or f"Skills and workflows for {category}."
        data.setdefault('categories', {})[category] = desc

    # 2. Register skill under names
    data.setdefault('names', {})[skill_name] = category

    with open(categories_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def convert(repo_source, custom_name=None, custom_category=None, category_desc=None, dest=None, categories_file=CATEGORIES_FILE):
    """Full conversion pipeline."""
    base_name = custom_name or os.path.basename(repo_source.rstrip('/\\').replace('.git', ''))
    skill_name = slugify(base_name)

    repo_dir, is_tmp = clone_or_read(repo_source)
    try:
        context, readme = extract_context(repo_dir)
        category = infer_category(skill_name, context, custom=custom_category)

        skill_md = distill_markdown(skill_name, category, context, readme)

        out_dir = dest or os.path.join(TEMPLATES_DIR, skill_name)
        os.makedirs(out_dir, exist_ok=True)
        skill_file = os.path.join(out_dir, 'SKILL.md')

        with open(skill_file, 'w', encoding='utf-8') as f:
            f.write(skill_md)

        register_skill_in_categories(skill_name, category, category_desc=category_desc, categories_file=categories_file)

        return {
            'skill_name': skill_name,
            'category': category,
            'skill_path': skill_file,
            'status': 'ok'
        }
    finally:
        if is_tmp:
            shutil.rmtree(repo_dir, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('repo', help='Git repository URL or local folder path')
    ap.add_argument('--category', help='Target category name (inferred if omitted)')
    ap.add_argument('--name', help='Custom skill name (inferred from repo name if omitted)')
    ap.add_argument('--desc', help='Description if creating a new category')
    ap.add_argument('--dest', help='Destination folder for the skill')
    ap.add_argument('--json', action='store_true', help='Output as JSON')
    args = ap.parse_args(argv)

    try:
        res = convert(args.repo, custom_name=args.name, custom_category=args.category, category_desc=args.desc, dest=args.dest)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"ok: Created skill '{res['skill_name']}' in category '{res['category']}'")
            print(f"    File: {res['skill_path']}")
    except Exception as e:
        if args.json:
            print(json.dumps({'error': str(e), 'status': 'fail'}))
        else:
            print(f"fail: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
