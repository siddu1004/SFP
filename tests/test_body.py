"""Finding skills by the full text of their SKILL.md (sfp_body).

Run:  python3 -m unittest discover -s tests -v
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_body  # noqa: E402
import sfp_hive as hive  # noqa: E402
import sfp_mcp as core  # noqa: E402


class BodyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = os.environ.get('SFP_DATA_DIR')
        os.environ['SFP_DATA_DIR'] = self.tmp
        self.file, self.skills = sfp_body._file, core.SKILLS
        core.SKILLS = {n: {'name': n, 'path': n} for n in ('alpha', 'beta', 'gamma')}
        texts = {'alpha': 'reconcile invoices with the ledger', 'beta': 'paint the fence', 'gamma': 'paint paint invoices'}
        for n, t in texts.items():
            with open(os.path.join(self.tmp, n + '.md'), 'w', encoding='utf-8') as f:
                f.write(t)
        sfp_body._file = lambda n: os.path.join(self.tmp, n + '.md')
        sfp_body._INDEX.clear()

    def tearDown(self):
        sfp_body._file, core.SKILLS = self.file, self.skills
        sfp_body._INDEX.clear()
        os.environ.pop('SFP_DATA_DIR', None)
        if self.saved is not None:
            os.environ['SFP_DATA_DIR'] = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_word_only_the_body_has_finds_the_skill(self):
        self.assertEqual(sfp_body.search('ledger')[0][1], 'alpha')
        self.assertEqual(sfp_body.search('nothingmatches'), [])

    def test_the_index_is_kept_and_rebuilt_when_a_skill_changes(self):
        sfp_body.search('paint')
        self.assertTrue(os.path.exists(sfp_body.cache_path()))
        with open(os.path.join(self.tmp, 'beta.md'), 'w', encoding='utf-8') as f:
            f.write('now about the ledger ledger ledger too')
        sfp_body._INDEX['seen'] = 0
        self.assertIn('beta', [n for _, n in sfp_body.search('ledger')])

    def test_a_broken_cache_or_a_missing_file_is_no_problem(self):
        with open(sfp_body.cache_path(), 'w') as f:
            f.write('not json')
        os.remove(os.path.join(self.tmp, 'gamma.md'))
        self.assertEqual(sfp_body.search('paint')[0][1], 'beta')


class ChoiceTest(unittest.TestCase):
    """The choice without a model."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = {k: os.environ.get(k) for k in ('SFP_DATA_DIR', 'SFP_SEMANTIC', 'SFP_FUSED')}
        os.environ.update(SFP_DATA_DIR=self.tmp, SFP_SEMANTIC='0')
        os.environ.pop('SFP_FUSED', None)
        sfp_body._INDEX.clear()

    def tearDown(self):
        sfp_body._INDEX.clear()
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_model_is_never_called_a_judge(self):
        res = hive.select('make my react page load faster')
        self.assertTrue(res['stack'])
        self.assertFalse([r for s in res['stack'] for r in s['reasons'] if 'local model' in r])

    def test_excluded_stays_out_and_pinned_stays_in(self):
        first = hive.select('make my react page load faster')['stack'][0]['name']
        res = hive.select('make my react page load faster', exclude=[first], include=['security-review'])
        names = [s['name'] for s in res['stack']]
        self.assertNotIn(first, names)
        self.assertIn('security-review', names)

    def test_the_old_choice_is_one_setting_away(self):
        os.environ['SFP_FUSED'] = '0'
        res = hive.select('make my react page load faster')
        self.assertFalse([r for s in res['stack'] for r in s['reasons'] if 'over every map' in r])

    def test_the_budget_holds_and_the_first_pick_always_stays(self):
        names = sorted(core.SKILLS)[:3]
        self.assertEqual(hive.within_budget(names, 1), names[:1])
        self.assertEqual(hive.within_budget(names, 10 ** 9), names)


if __name__ == '__main__':
    unittest.main()
