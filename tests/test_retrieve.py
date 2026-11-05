"""Candidates and the model's judgement (sfp_retrieve). Every model is a fake, so these run offline.

Run:  python3 -m unittest discover -s tests -v
"""
import os
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault('SFP_DATA_DIR', tempfile.mkdtemp(prefix='sfp-test-'))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_intent  # noqa: E402
import sfp_mcp as core  # noqa: E402
import sfp_retrieve as rt  # noqa: E402


class FusionTest(unittest.TestCase):
    def test_a_skill_in_both_rankings_beats_one_first_in_only_one(self):
        self.assertEqual(rt.rrf([(['a', 'b'], 1.0), (['c', 'b'], 1.0)])[0], 'b')

    def test_clauses_split_only_real_jobs(self):
        self.assertEqual(rt.clauses('rename this variable'), [])
        self.assertEqual(len(rt.clauses('build the signup page with tests, deploy it and check security')), 3)

    def test_candidates_keep_specialist_fields_out_unless_asked(self):
        self.addCleanup(setattr, rt, '_rank_words', rt._rank_words)
        self.addCleanup(setattr, rt, '_rank_meaning', rt._rank_meaning)
        rt._rank_words = lambda text: ['career-ops', 'security-review']
        rt._rank_meaning = lambda text: ['security-review']
        self.assertEqual(rt.candidates('make the login safe'), ['security-review'])
        self.assertIn('career-ops', rt.candidates('help with my career change'))

    def test_the_caller_can_rule_skills_out(self):
        self.addCleanup(setattr, rt, '_rank_words', rt._rank_words)
        self.addCleanup(setattr, rt, '_rank_meaning', rt._rank_meaning)
        rt._rank_words = lambda text: ['rust-testing', 'react-testing']
        rt._rank_meaning = lambda text: []
        self.assertEqual(rt.candidates('write tests', allow=lambda n: n != 'rust-testing'), ['react-testing'])

    def test_project_tech_filters_skills_with_conflicting_needs(self):
        self.addCleanup(setattr, rt, '_rank_words', rt._rank_words)
        self.addCleanup(setattr, rt, '_rank_meaning', rt._rank_meaning)
        self.addCleanup(setattr, rt, 'cards', rt.cards)
        rt._rank_words = lambda text: ['python-testing', 'rust-testing']
        rt._rank_meaning = lambda text: []
        rt.cards = lambda: {'python-testing': {'needs': ['pytest']}, 'rust-testing': {'needs': []}}
        # When project_tech is rust and task does not name pytest, python-testing is filtered out
        self.assertEqual(rt.candidates('write unit tests', project_tech=('rust',)), ['rust-testing'])

    def test_candidates_combines_first_clause_ranking(self):
        calls = []
        self.addCleanup(setattr, rt, '_rank_words', rt._rank_words)
        self.addCleanup(setattr, rt, '_rank_meaning', rt._rank_meaning)
        rt._rank_words = lambda text, limit=60: calls.append(text) or ['rust-testing']
        rt._rank_meaning = lambda text, limit=60: []
        rt.candidates('build signup page, then write tests')
        self.assertIn('build signup page', calls)


class JudgeTest(unittest.TestCase):
    NAMES = ['security-review', 'react-testing', 'rust-testing']

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = {k: os.environ.get(k) for k in ('SFP_DATA_DIR', 'SFP_SEMANTIC')}
        os.environ['SFP_DATA_DIR'] = self.tmp
        os.environ['SFP_SEMANTIC'] = '1'
        self.chat, self.model = sfp_intent.chat, sfp_intent.model_cached
        sfp_intent.model_cached = lambda: {'base_url': 'x', 'model': 'fake', 'key_env': ''}
        self.calls = []

    def tearDown(self):
        sfp_intent.chat, sfp_intent.model_cached = self.chat, self.model
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def answer(self, text):
        def fake(ep, prompt, tokens, timeout):
            self.calls.append(prompt)
            return text
        sfp_intent.chat = fake

    def test_parsing_keeps_order_and_ignores_bad_numbers(self):
        self.assertEqual(rt.parse_picks('3, 1, 9, 0, 3', self.NAMES), ['rust-testing', 'security-review'])
        self.assertEqual(rt.parse_picks('<think>use 2</think> 1', self.NAMES), ['security-review'])

    def test_zero_means_none_fits(self):
        self.answer('0')
        self.assertEqual(rt.judge('bake bread', self.NAMES), [])

    def test_the_answer_is_cached(self):
        self.answer('2')
        self.assertEqual(rt.judge('write tests', self.NAMES), ['react-testing'])
        self.assertEqual(rt.judge('write tests', self.NAMES), ['react-testing'])
        self.assertEqual(len(self.calls), 1)

    def test_no_answer_is_no_judgement_not_an_empty_result(self):
        def fail(ep, prompt, tokens, timeout):
            raise OSError('down')
        sfp_intent.chat = fail
        self.assertIsNone(rt.judge('write tests', self.NAMES))
        self.answer('<think>still reasoning</think>')
        self.assertIsNone(rt.judge('write more tests', self.NAMES))

    def test_no_model_is_no_judgement(self):
        sfp_intent.model_cached = lambda: None
        self.assertIsNone(rt.judge('write tests', self.NAMES))

    def test_the_prompt_shows_each_guide_and_the_project(self):
        self.answer('1')
        rt.judge('write tests', self.NAMES, tech=('rust',))
        self.assertIn('Project technologies: rust', self.calls[0])
        self.assertIn('1. security-review', self.calls[0])

    def test_sfp_intent_judge_delegates_and_parses_order(self):
        self.answer('3, 1')
        res = sfp_intent.judge('write tests', self.NAMES)
        self.assertEqual(res, ['rust-testing', 'security-review'])

    def test_sfp_intent_judge_zero_means_empty_list(self):
        self.answer('0')
        res = sfp_intent.judge('make pasta', self.NAMES)
        self.assertEqual(res, [])

    def test_sfp_intent_judge_timeout_returns_none(self):
        def fail(ep, prompt, tokens, timeout):
            raise OSError('timeout')
        sfp_intent.chat = fail
        res = sfp_intent.judge('write tests', self.NAMES)
        self.assertIsNone(res)


if __name__ == '__main__':
    unittest.main()
