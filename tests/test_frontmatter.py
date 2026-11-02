"""Every generated skill opens with frontmatter an agent can parse, holding its name and a description.

A SKILL.md with no frontmatter breaks agents: a parser takes the first pair of `---` rules in the body as YAML and
fails ("mapping values are not allowed"), and the skill has no description to be found by. scripts/sync.py adds
frontmatter to any upstream skill that has none.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import sync  # noqa: E402

FRONT = re.compile(r'^---\s*\n(.*?)\n---[ \t]*\n', re.S)


class FrontmatterTest(unittest.TestCase):
    def test_every_skill_has_frontmatter_with_its_name_and_a_description(self):
        with open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8') as f:
            skills = json.load(f)['skills']
        for s in skills:
            with open(os.path.join(ROOT, s['path'], 'SKILL.md'), encoding='utf-8', errors='replace') as f:
                m = FRONT.match(f.read())
            self.assertIsNotNone(m, '%s has no frontmatter' % s['name'])
            self.assertEqual(sync.field(m.group(1), 'name'), s['name'])
            self.assertTrue(s['description'], '%s has no description' % s['name'])

    def test_every_frontmatter_parses_as_strict_yaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML is not installed')
        with open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8') as f:
            skills = json.load(f)['skills']
        for s in skills:
            with open(os.path.join(ROOT, s['path'], 'SKILL.md'), encoding='utf-8', errors='replace') as f:
                m = FRONT.match(f.read())
            try:
                yaml.safe_load(m.group(1))
            except yaml.YAMLError as e:
                self.fail('%s: %s' % (s['name'], str(e).splitlines()[0]))

    def test_a_description_with_a_colon_is_quoted_and_reads_back_the_same(self):
        import tempfile
        desc = 'Search in three steps: search, timeline. Ask "did we solve this?" # not a comment'
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'SKILL.md'), 'w', encoding='utf-8') as f:
                f.write('---\nname: demo\ndescription: %s\n---\n\nBody: here.\n' % desc)
            sync.quote_description(d)
            with open(os.path.join(d, 'SKILL.md'), encoding='utf-8') as f:
                text = f.read()
        fm = FRONT.match(text).group(1)
        self.assertEqual(sync.field(fm, 'description'), desc)
        self.assertTrue(text.endswith('Body: here.\n'))

    def test_a_skill_without_frontmatter_gets_one_that_survives_colons_and_rules(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            body = ('> a note\n\n# Title\n\nSets up the thing: fast. Needs bun.\n\n---\n\n'
                    'If you do not have it: install it.\n\n---\n')
            with open(os.path.join(d, 'SKILL.md'), 'w', encoding='utf-8') as f:
                f.write(body)
            fm = sync.add_frontmatter(d, 'demo')
            with open(os.path.join(d, 'SKILL.md'), encoding='utf-8') as f:
                text = f.read()
        self.assertEqual(FRONT.match(text).group(1), fm)
        self.assertEqual(sync.field(fm, 'name'), 'demo')
        self.assertEqual(sync.field(fm, 'description'), 'Sets up the thing: fast. Needs bun.')
        self.assertTrue(text.endswith(body))
        try:
            import yaml
        except ImportError:
            return
        self.assertEqual(yaml.safe_load(fm)['description'], 'Sets up the thing: fast. Needs bun.')


if __name__ == '__main__':
    unittest.main()
