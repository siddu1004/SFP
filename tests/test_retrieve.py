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


class FusedPicksTest(unittest.TestCase):
    def test_both_rankings_count_and_what_cannot_fit_stays_out(self):
        self.addCleanup(setattr, rt, '_rank_words', rt._rank_words)
        rt._rank_words = lambda text, limit=80: ['react-testing', 'security-review', 'rust-testing']
        similar = [(0.9, 'security-review'), (0.8, 'react-testing'), (0.7, 'not-a-skill'), (0.6, 'python-testing')]
        picks = rt.fused_picks('write tests', similar, allow=lambda n: n != 'react-testing')
        self.assertEqual(picks[0], 'security-review')
        self.assertNotIn('react-testing', picks)
        self.assertNotIn('not-a-skill', picks)
        self.assertLessEqual(len(picks), rt.FUSED_PICKS)

    def test_no_model_is_asked_unless_the_user_wants_it(self):
        import sfp_hive
        saved = os.environ.pop('SFP_RERANK', None)
        try:
            self.assertFalse(sfp_hive.rerank_wanted({'text': 'x', 'words_weak': True}))
            os.environ['SFP_RERANK'] = '1'
            self.assertTrue(sfp_hive.rerank_wanted({'text': 'x', 'words_weak': True}))
        finally:
            os.environ.pop('SFP_RERANK', None)
            if saved is not None:
                os.environ['SFP_RERANK'] = saved


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


class WaitTest(unittest.TestCase):
    """A task never waits long for a model: only a loaded one is asked, and one that fails is left alone for a while."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = {k: os.environ.pop(k, None) for k in ('SFP_DATA_DIR', 'SFP_REWRITE_URL', 'SFP_REWRITE_MODEL', 'SFP_RERANK', 'SFP_SEMANTIC')}
        os.environ['SFP_DATA_DIR'] = self.tmp
        self.found, self.chat, self.get_json = sfp_intent.found, sfp_intent.chat, sfp_intent.sfp_embed._get_json
        sfp_intent._MODEL['checked'] = 0.0

    def tearDown(self):
        sfp_intent.found, sfp_intent.chat, sfp_intent.sfp_embed._get_json = self.found, self.chat, self.get_json
        sfp_intent._MODEL['checked'] = 0.0
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def models(self, *rows):
        sfp_intent._MODEL['checked'] = 0.0
        sfp_intent.found = lambda timeout=1.0, for_tasks=False: [
            {'base_url': 'http://x/v1', 'model': m, 'runtime': runtime, 'loaded': loaded, 'key_env': ''} for m, runtime, loaded in rows]

    def test_a_model_that_is_not_loaded_is_not_asked(self):
        self.models(('cold-7b', 'LM Studio', False))
        self.assertIsNone(sfp_intent.model_cached())
        self.models(('cold-7b', 'LM Studio', False), ('warm-7b', 'LM Studio', True))
        self.assertEqual(sfp_intent.model_cached()['model'], 'warm-7b')

    def test_an_ollama_model_counts_only_when_held_in_memory(self):
        sfp_intent.sfp_embed._get_json = lambda url, timeout: {'models': [{'name': 'warm:7b'}]}
        self.models(('cold:7b', 'Ollama', None), ('warm:7b', 'Ollama', None))
        self.assertEqual(sfp_intent.model_cached()['model'], 'warm:7b')

    def test_asking_always_may_load_one(self):
        os.environ['SFP_RERANK'] = '1'
        self.models(('cold-7b', 'LM Studio', False))
        self.assertEqual(sfp_intent.model_cached()['model'], 'cold-7b')

    def test_a_model_that_fails_is_left_alone_then_tried_again(self):
        self.models(('warm-7b', 'LM Studio', True))

        def fail(ep, prompt, tokens, timeout):
            raise TimeoutError('slow')
        sfp_intent.chat = fail
        self.assertIsNone(rt.judge('write tests', ['react-testing']))
        self.assertIsNone(sfp_intent.model_cached(), 'resting after a timeout')
        sfp_intent.cool_down(-1)
        self.assertEqual(sfp_intent.model_cached()['model'], 'warm-7b')


if __name__ == '__main__':
    unittest.main()
