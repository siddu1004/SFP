"""The generated README: the banner stays as designed, every figure and link in it is real.

These tests exist because a README can look fine and still be wrong: a table can end up in the wrong
place, a placeholder can go unfilled, a link can point at nothing.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(ROOT, 'README.md'), encoding='utf-8') as _f:
    README = _f.read()
with open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8') as _f:
    CATALOG = json.load(_f)
SKILLS = {s['name']: s for s in CATALOG['skills']}

BANNER = '''<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img src="assets/banner-light.svg" alt="SFP: Skills for Productivity" width="100%">
  </picture>
</h1>
'''


def section(title):
    m = re.search(r'^## %s\n(.*?)(?=^## |\Z)' % re.escape(title), README, re.M | re.S)
    assert m, 'no section called %s' % title
    return m.group(1)


class ReadmeTest(unittest.TestCase):
    def test_banner_is_exactly_as_designed(self):
        self.assertTrue(README.startswith(BANNER))

    def test_no_placeholder_is_left_unfilled(self):
        self.assertNotIn('@@', README)

    def test_no_emoji_and_no_dashes_used_as_punctuation(self):
        self.assertEqual(re.findall('[–—\U0001F300-\U0001FAFF☀-➿]', README), [])

    def test_every_local_link_exists(self):
        for link in re.findall(r'\]\((?!http|#|mailto)([^)#]+)', README):
            self.assertTrue(os.path.exists(os.path.join(ROOT, link)), link)

    def test_every_anchor_resolves(self):
        heads = {re.sub(r'[^\w\s-]', '', h.lower()).strip().replace(' ', '-') for h in re.findall(r'^#{1,6} (.+)$', README, re.M)}
        for anchor in re.findall(r'\]\(#([^)]+)\)', README):
            self.assertIn(anchor, heads)

    def test_the_cost_table_is_where_it_says_it_is(self):
        proof = section('The Proof')
        cost = proof.split('**What does it cost your agent?**')[1].split('**How fast is it?**')[0]
        self.assertIn('Skill descriptions it carries each session', cost)
        self.assertIn('`sfp` and `sfp-select` only', cost)
        self.assertIn('`everything`', cost)
        self.assertNotIn('The selector chooses', cost)  # the five-project table lives in "See It Choose"

    def test_each_table_appears_once(self):
        self.assertEqual(README.count('| Your project | The selector chooses |'), 1)
        self.assertEqual(README.count('Skill descriptions it carries each session'), 1)
        self.assertEqual(README.count('| Task set |'), 1)

    def test_the_five_project_table_names_real_skills_for_the_right_project(self):
        rows = re.findall(r'^\| (Next\.js|Rust|\.NET|Flutter|Django) \| (.+) \|$', section('See It Choose'), re.M)
        self.assertEqual(len(rows), 5)
        own = {'Next.js': 'react', 'Rust': 'rust', '.NET': 'csharp', 'Flutter': 'flutter', 'Django': 'django'}
        for label, cell in rows:
            names = re.findall(r'`([^`]+)`', cell)
            self.assertTrue(names, label)
            for n in names:
                self.assertIn(n, SKILLS, label)
            # The skill for this very technology is in the stack.
            self.assertTrue(any(own[label] in n for n in names), (label, names))

    def test_skills_named_in_prose_exist(self):
        who = section('Who It Is For')
        for name in re.findall(r'`([a-z0-9-]+)`', who):
            if name in ('frontend-dev', 'backend-dev', 'mobile-dev', 'agent-builder', 'security', 'business-ops',
                        'content-media', 'career'):
                continue
            self.assertIn(name, SKILLS, name)

    def test_headline_numbers_match_the_catalog(self):
        self.assertIn('%d skills' % len(SKILLS), README)

    def test_the_limits_are_stated(self):
        self.assertIn('What has not been measured', README)
        self.assertIn('Learning is measured on a simulated user', README)
        self.assertIn('Whether the chosen skills make your agent', README)


if __name__ == '__main__':
    unittest.main()
