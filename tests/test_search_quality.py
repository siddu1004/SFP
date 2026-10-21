"""Search ranking: tokenization behaviours and a quality floor over the task sets in tests/.

The README quotes search accuracy computed from the same task sets, so these
tests keep that claim honest: a ranking change that makes search worse fails here.

Run:  python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['SFP_ROOT'] = ROOT
_spec = importlib.util.spec_from_file_location('sfp_mcp_quality', os.path.join(ROOT, 'mcp', 'sfp_mcp.py'))
mcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mcp)


def top(query, k=3):
    return [s['name'] for s in mcp.search(query, limit=k)]


class TokenizationTest(unittest.TestCase):
    def test_symbol_names_stay_searchable(self):
        self.assertIn('cpp-testing', top('write C++ unit tests'))
        self.assertEqual(top('C# testing', 1), ['csharp-testing'])
        self.assertEqual(top('.NET patterns', 1), ['dotnet-patterns'])

    def test_plural_and_singular_match(self):
        self.assertEqual(top('dark patterns', 1), ['dark-pattern-check'])

    def test_filler_words_alone_match_nothing(self):
        self.assertEqual(mcp.search('for my a to the'), [])
        self.assertEqual(mcp.tokens('How do I set up the thing'), ['set', 'thing'])

    def test_filler_words_do_not_drag_in_unrelated_skills(self):
        self.assertIn('docker-patterns', top('set up docker for a python app'))

    def test_find_api_keeps_the_users_own_words(self):
        self.assertEqual(mcp.raw_words('--help; cats'), ['help', 'cats'])


class QualityFloorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = []
        for name in ('search_eval.json', 'search_holdout.json', 'search_fresh.json'):
            with open(os.path.join(ROOT, 'tests', name), encoding='utf-8') as f:
                cls.cases += json.load(f)

    def test_every_case_has_at_least_one_real_skill(self):
        for case in self.cases:
            self.assertTrue(any(x in mcp.SKILLS for x in case['expect']), case['task'])

    def hit_rate(self, k):
        hits = 0
        for case in self.cases:
            want = {x for x in case['expect'] if x in mcp.SKILLS}
            if want & set(top(case['task'], k)):
                hits += 1
        return hits / len(self.cases)

    def test_the_right_skill_is_usually_in_the_top_three(self):
        self.assertGreaterEqual(self.hit_rate(3), 0.85)

    def test_the_right_skill_is_usually_in_the_top_five(self):
        self.assertGreaterEqual(self.hit_rate(5), 0.88)

    def test_the_right_skill_is_often_first(self):
        self.assertGreaterEqual(self.hit_rate(1), 0.70)


if __name__ == '__main__':
    unittest.main()
