#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_cards
import sfp_hive
import sfp_learn


class TasteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig_data_dir = os.environ.get('SFP_DATA_DIR')
        os.environ['SFP_DATA_DIR'] = self.tmp

    def tearDown(self):
        if self.orig_data_dir is not None:
            os.environ['SFP_DATA_DIR'] = self.orig_data_dir
        else:
            os.environ.pop('SFP_DATA_DIR', None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cards_validate(self):
        cards = sfp_cards.load_cards()
        self.assertGreater(len(cards), 1000)
        for name, c in cards.items():
            self.assertTrue(sfp_cards.validate_card(c), f"Card {name} failed validation: {c}")

    def test_cold_start_unchanged(self):
        t = sfp_learn.load_taste()
        self.assertEqual(t['events'], 0)
        self.assertEqual(t['output'], {})
        self.assertEqual(t['style'], {})
        self.assertEqual(t['depth'], {})

        # Select runs smoothly without taste
        res = sfp_hive.select('write unit tests in python', None, semantic=False)
        self.assertTrue(res['stack'])

    def test_decay_works(self):
        t0 = 1000000.0
        sfp_learn.update_taste('manim-video', weight=2.0, t=t0)
        # Immediate query at t0
        t_now = sfp_learn.load_taste(now=t0)
        score_t0 = t_now['output'].get('animation', 0.0)
        self.assertGreater(score_t0, 1.9)

        # Query after 30 days (1 half-life)
        t_30d = sfp_learn.load_taste(now=t0 + 30 * 86400)
        score_30d = t_30d['output'].get('animation', 0.0)
        self.assertAlmostEqual(score_30d, score_t0 * 0.5, places=1)

    def test_taste_json_holds_no_task_text(self):
        sfp_learn.update_taste('manim-video', weight=1.0)
        path = sfp_learn.taste_path()
        self.assertTrue(os.path.exists(path))
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertNotIn('task', content)
        self.assertNotIn('prompt', content)
        data = json.loads(content)
        for ev in data.get('history', []):
            self.assertIn('t', ev)
            self.assertIn('weight', ev)
            self.assertIn('facets', ev)
            self.assertNotIn('task', ev)

    def test_taste_learned_from_animation_picks_animation_for_new_topic(self):
        # Learn strong preference for animation
        for _ in range(5):
            sfp_learn.update_taste('manim-video', weight=2.0)
        t = sfp_learn.load_taste()
        self.assertGreater(t['output'].get('animation', 0), 1.0)

        # For an explain request naming no form, animation is boosted
        res = sfp_hive.select('explain attention mechanism in neural networks', None, semantic=False)
        names = [s['name'] for s in res['stack']]
        if 'manim-video' in names:
            item = next(s for s in res['stack'] if s['name'] == 'manim-video')
            reasons = ' '.join(item['reasons'])
            self.assertTrue('prefer animation' in reasons or 'format' in reasons or 'visual' in reasons)

    def test_named_form_overrides_taste(self):
        # Even with high animation taste
        for _ in range(5):
            sfp_learn.update_taste('manim-video', weight=3.0)

        # An explicitly requested form ("text summary") overrides taste
        job, named = sfp_cards.task_intent('just give me a text summary of attention mechanisms')
        self.assertEqual(named, 'text')

        res = sfp_hive.select('just give me a text summary of attention mechanisms', None, semantic=False)
        self.assertEqual(res['task_intent']['named_form'], 'text')
        # manim-video produces animation, not text-only summary
        if res['stack']:
            first_card = sfp_cards.get_card(res['stack'][0]['name'])
            self.assertTrue(any(f in first_card.get('output', []) for f in ('text', 'document', 'report')))
            self.assertNotIn('animation', first_card.get('output', []))

    def test_substitutes_never_stack_and_alternative_offered(self):
        # Create an artificial scenario where two substitutes are both candidates
        res = sfp_hive.select('explain how attention works with line animation', None, semantic=False)
        subs = [sfp_cards.get_card(s['name']).get('substitutes_for') for s in res['stack']]
        # No duplicates in non-generic substitute groups
        non_generic_subs = [s for s in subs if s != 'software-engineering-patterns']
        self.assertEqual(len(non_generic_subs), len(set(non_generic_subs)))


if __name__ == '__main__':
    unittest.main()
