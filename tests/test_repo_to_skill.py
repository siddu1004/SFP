"""The Git-to-skill converter (scripts/repo_to_skill.py): a skill written from the README with its real commands, a local model
used when one answers well, nothing in the checkout changed by default, and tools that can be installed into.

Run:  python3 -m unittest discover -s tests -v
"""
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import repo_to_skill as rts  # noqa: E402

README = """# PromptKit

PromptKit is a CLI that lints and versions LLM prompts. It runs offline.

## Install

```bash
pip install promptkit
promptkit init
```

## Usage

```bash
promptkit lint prompts/
promptkit diff v1 v2
```

Set `PROMPTKIT_API_KEY` to enable cloud sync.

## License

MIT
"""


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.tmp, 'sample-repo')
        os.makedirs(self.repo_dir)
        with open(os.path.join(self.repo_dir, 'README.md'), 'w', encoding='utf-8') as f:
            f.write(README)
        with open(os.path.join(self.repo_dir, 'package.json'), 'w', encoding='utf-8') as f:
            f.write('{"name": "sample-ui", "version": "1.0.0"}')
        self.old = os.environ.get('SFP_DATA_DIR')
        os.environ['SFP_DATA_DIR'] = os.path.join(self.tmp, 'data')

    def tearDown(self):
        if self.old is None:
            os.environ.pop('SFP_DATA_DIR', None)
        else:
            os.environ['SFP_DATA_DIR'] = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)


class FromReadmeTest(Case):
    def test_the_skill_carries_the_real_commands_and_variables(self):
        context, readme = rts.extract_context(self.repo_dir)
        md = rts.distill_markdown('promptkit', 'ai-ml', context, readme)
        self.assertTrue(md.startswith('---'))
        for want in ('name: promptkit', 'pip install promptkit', 'promptkit lint prompts/', 'PROMPTKIT_API_KEY', '## When to use'):
            self.assertIn(want, md)
        self.assertNotIn('git clone https://github.com/...', md)
        self.assertNotIn('Keep component boundaries clean', md)      # no generic filler

    def test_the_header_is_valid_yaml_whatever_the_readme_says(self):
        md = rts.distill_markdown('x', 'c', '', '# X\n\nA tool that says "hello": and more, for #1 users.\n')
        header = md.split('---')[1]
        desc = [l for l in header.splitlines() if l.startswith('description:')][0][len('description:'):].strip()
        self.assertEqual(json.loads(desc)[:6], 'A tool')                # a double-quoted scalar that round-trips

    def test_categories_and_names(self):
        context, _ = rts.extract_context(self.repo_dir)
        self.assertEqual(rts.infer_category('sample-ui', 'A React UI library with components'), 'frontend')
        self.assertEqual(rts.infer_category('x', '', custom='mine'), 'mine')
        self.assertEqual(rts.infer_category('x', 'nothing relevant here'), 'engineering')
        self.assertEqual(rts.slugify('My Cool_Repo!'), 'my-cool-repo')


class ConvertTest(Case):
    def test_it_writes_to_the_data_folder_and_leaves_the_checkout_alone(self):
        cats = os.path.join(self.tmp, 'categories.json')
        with open(cats, 'w', encoding='utf-8') as f:
            json.dump({'categories': {'frontend': 'UI'}, 'names': {}}, f)
        res = rts.convert(self.repo_dir, categories_file=cats)
        self.assertEqual(res['status'], 'ok')
        self.assertEqual(res['skill_path'], os.path.join(self.tmp, 'data', 'skills', 'sample-repo', 'SKILL.md'))
        with open(cats, encoding='utf-8') as f:
            self.assertEqual(json.load(f)['names'], {})                # not registered unless asked

    def test_register_adds_it_to_the_categories(self):
        cats = os.path.join(self.tmp, 'categories.json')
        with open(cats, 'w', encoding='utf-8') as f:
            json.dump({'categories': {}, 'names': {}}, f)
        res = rts.convert(self.repo_dir, custom_category='mine', category_desc='My things', dest=os.path.join(self.tmp, 'out'),
                          categories_file=cats, register=True)
        with open(cats, encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data['names'], {'sample-repo': 'mine'})
        self.assertEqual(data['categories']['mine'], 'My things')
        self.assertTrue(res['registered'])

    def test_install_copies_the_skill_into_a_tools_folder(self):
        import install as sfp_install
        target = os.path.join(self.tmp, 'tool-skills')
        old = sfp_install.TOOLS['claude']
        sfp_install.TOOLS['claude'] = old[:2] + (target,) + old[3:]
        try:
            res = rts.convert(self.repo_dir, dest=os.path.join(self.tmp, 'out'), install=['claude'])
        finally:
            sfp_install.TOOLS['claude'] = old
        self.assertTrue(os.path.isfile(os.path.join(target, 'sample-repo', 'SKILL.md')))
        self.assertEqual(list(res['installed']), ['claude'])
        with self.assertRaises(ValueError):
            rts.install_into(os.path.join(self.tmp, 'out'), 'x', ['no-such-tool'])

    def test_a_failed_clone_is_an_error_not_a_crash(self):
        import subprocess
        with self.assertRaises(RuntimeError):
            rts.clone_or_read('http://127.0.0.1:1/none.git')
        for extra, stream in (([], 'stderr'), (['--json'], 'stdout')):
            out = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'repo_to_skill.py'), 'http://127.0.0.1:1/none.git'] + extra,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 1)
            self.assertIn('Could not clone', getattr(out, stream))
            self.assertNotIn('NameError', out.stderr)


class LocalModelTest(Case):
    def serve(self, answer):
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                data = json.dumps({'data': [{'id': 'qwen2.5-coder:7b'}, {'id': 'llama-3.1-70b-instruct'}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.asked = body['model']
                data = json.dumps({'choices': [{'message': {'content': answer}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=srv.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        base = 'http://127.0.0.1:%d/v1' % srv.server_address[1]
        return [('fake', 'Fake', base, base + '/models')]

    def test_the_strongest_local_model_writes_the_skill_and_its_name_is_enforced(self):
        runtimes = self.serve('```markdown\n---\nname: wrong-name\ndescription: "Use when linting prompts."\n---\n\n# Prompts\n```')
        out = rts.query_local_llm('write it', 'promptkit', runtimes=runtimes)
        self.assertIn('name: promptkit', out)
        self.assertNotIn('wrong-name', out)
        self.assertEqual(self.asked, 'llama-3.1-70b-instruct')       # the 70b model, not the 7b

    def test_an_answer_without_a_valid_header_is_ignored(self):
        runtimes = self.serve('Sure! Here is a skill for you.')
        self.assertIsNone(rts.query_local_llm('write it', 'promptkit', runtimes=runtimes))

    def test_no_local_model_means_no_answer_and_the_readme_is_used(self):
        self.assertIsNone(rts.query_local_llm('x', 'y', runtimes=[('none', 'None', 'http://127.0.0.1:1/v1', 'http://127.0.0.1:1/v1/models')]))


if __name__ == '__main__':
    unittest.main()
