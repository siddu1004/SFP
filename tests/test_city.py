"""The skill city: stories, maps, towers, the selector and its learning (sfp_city).

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_body  # noqa: E402
import sfp_city as city  # noqa: E402
import sfp_hive as hive  # noqa: E402
import sfp_learn  # noqa: E402
import sfp_mcp as core  # noqa: E402

TASK = 'make my react page load faster'


class CityCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        names = ('SFP_DATA_DIR', 'SFP_SEMANTIC', 'SFP_FUSED', 'SFP_NO_LEARNING', 'SFP_NO_USAGE_LOG', 'SFP_MAP')
        self.saved = {k: os.environ.pop(k, None) for k in names}
        os.environ.update(SFP_DATA_DIR=self.tmp, SFP_SEMANTIC='0')
        sfp_body._INDEX.clear()

    def tearDown(self):
        sfp_body._INDEX.clear()
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)


class StoryTest(CityCase):
    def test_every_skill_has_a_story(self):
        for name in core.SKILLS:
            s = city.story(name)
            self.assertTrue(s['does'] and s['tower'] and s['district'] and s['tokens'] is not None, name)
            self.assertTrue(s['activates_on'], name)
            self.assertNotIn(name, s['next_to'])
        self.assertEqual(city.story('not-a-skill'), {})

    def test_the_shipped_data_matches_the_library_and_the_maps(self):
        d = city.data()
        self.assertEqual(set(d['keys']), set(core.SKILLS))
        for near in d['near'].values():
            self.assertTrue(all(n in core.SKILLS for n, _ in near))
            self.assertAlmostEqual(sum(w for _, w in near), 1.0, places=2)
        self.assertEqual(len(d['weights']['text']), 2 * len(city.TEXT_MAPS) + 3)
        self.assertEqual(len(d['weights']['model']), 2 * len(city.TEXT_MAPS + city.MEANING_MAPS) + 3)


class MapTest(CityCase):
    def test_heights_fall_with_rank_and_stay_between_0_and_1(self):
        high, rise = city._heights({'a': 9.0, 'b': 3.0, 'c': 1.0})
        self.assertEqual(high['a'], 1.0)
        self.assertGreater(high['b'], high['c'])
        self.assertTrue(all(0 <= v <= 1 for v in rise.values()))
        self.assertEqual(city._heights({}), ({}, {}))

    def test_the_policy_is_a_probability(self):
        p = city.policy({'a': 1.0, 'b': 0.5, 'c': -3.0})
        self.assertAlmostEqual(sum(p.values()), 1.0)
        self.assertGreater(p['a'], p['b'])
        self.assertEqual(city.policy({}), {})

    def test_meaning_adds_its_maps(self):
        near = {n: (0.9 if n == 'react-performance' else 0.1, 0.2, 0.2) for n in core.SKILLS}
        self.assertEqual(city.rank(TASK)[2], 'text')
        order, _, kind, f = city.rank(TASK, near)
        self.assertEqual(kind, 'model')
        self.assertEqual(len(f[order[0]]), len(city.data()['weights']['model']))

    def test_towers_hold_the_best_and_leave_out_what_is_skipped(self):
        order, score, _, _ = city.rank(TASK)
        rows = city.towers(order, score, skip={order[0]})
        names = [x['name'] for t in rows for x in t['floors']]
        self.assertEqual(sorted(names), sorted(order[1:1 + city.MAP_SIZE]))
        heights = [t['height'] for t in rows]
        self.assertEqual(heights, sorted(heights, reverse=True))

    def test_what_is_not_allowed_is_not_in_the_city(self):
        order = city.rank(TASK)[0]
        self.assertNotIn(order[0], city.rank(TASK, allow=lambda n: n != order[0])[0])


class LearningTest(CityCase):
    F = [[1.0, 0.0], [0.0, 1.0]]

    def test_reward_moves_weights_towards_what_helped_and_never_far(self):
        w = [0.2, 0.2]
        up = city.update(w, w, ['a', 'b'], self.F, {'b': 1.0})
        self.assertGreater(up[1], w[1])
        self.assertLess(up[0], w[0])
        for _ in range(500):
            w = city.update(w, [0.2, 0.2], ['a', 'b'], self.F, {'b': 1.0})
        self.assertTrue(all(abs(x - 0.2) <= city.REACH + 1e-4 for x in w))

    def test_feedback_teaches_the_selector_and_forget_unlearns(self):
        res = sfp_learn.decide(TASK)
        row = city.recall(res['decision'])
        self.assertTrue(row and len(row['names']) <= city.KEEP)
        self.assertNotIn('react page', json.dumps(row))
        size = len(row['f'][0])
        before = city.weights(row['kind'], size)
        sfp_learn.give_feedback(res['decision'], missing=[row['names'][3]], unhelpful=[row['names'][0]])
        self.assertNotEqual(city.weights(row['kind'], size), before)
        sfp_learn.forget()
        self.assertEqual(city.weights(row['kind'], size), city.shipped_weights(row['kind'], size))
        self.assertIsNone(city.recall(res['decision']))

    def test_nothing_is_kept_when_learning_is_off(self):
        os.environ['SFP_NO_LEARNING'] = '1'
        sfp_learn.decide(TASK)
        self.assertFalse(os.path.exists(city._log_path()))
        self.assertFalse(city.learn('d_x', ['react-performance']))

    def test_a_broken_weights_file_is_ignored(self):
        for bad in ('not json', '[]', '{"text": [99]}', '{"text": null}'):
            with open(city._weights_path(), 'w') as f:
                f.write(bad)
            size = len(city.data()['weights']['text'])
            self.assertEqual(city.weights('text', size), city.shipped_weights('text', size))


class NoSkillTest(CityCase):
    def test_nothing_matches_means_no_skill_selected_and_says_why(self):
        res = hive.select('fix a typo in the readme')
        if res['stack']:
            res = hive.select('for the of a')
        self.assertEqual(res['stack'], [])
        self.assertEqual(res['status'], 'no skill selected')
        self.assertTrue(res['why_none'])
        self.assertEqual(res['city'], [])
        self.assertIn('No skill selected', hive.format_stack(res))

    def test_a_match_is_selected_and_the_map_leaves_out_the_picks(self):
        res = hive.select(TASK)
        self.assertEqual(res['status'], 'selected')
        self.assertIsNone(res['why_none'])
        on_map = {x['name'] for t in res['city'] for x in t['floors']}
        self.assertTrue(on_map)
        self.assertFalse(on_map & {s['name'] for s in res['stack']})

    def test_the_mcp_tool_gives_the_map_and_names_the_empty_answer(self):
        out = json.loads(core.tool_select_skills({'task': TASK}))
        self.assertTrue(out['map'])
        self.assertNotIn('city', out)
        os.environ['SFP_MAP'] = '0'
        self.assertNotIn('map', json.loads(core.tool_select_skills({'task': TASK})))


if __name__ == '__main__':
    unittest.main()
