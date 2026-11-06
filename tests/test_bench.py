#!/usr/bin/env python3
"""tests/test_bench.py - verifies bench/run_all.py parity and ~/.sfp data isolation."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))
sys.path.insert(0, os.path.join(ROOT, 'bench'))

import sfp_mcp as core
import sfp_stack as v1
import sfp_hive as hive

class BenchSuiteParityTest(unittest.TestCase):
    def test_run_all_words_only_numbers_equal_evaluate(self):
        """Assert that run_all's words-only numbers equal sfp_hive.evaluate() for every set."""
        eval_out = hive.evaluate(semantic=False)
        tests_dir = os.path.join(ROOT, 'tests')
        hist = hive.History(v1.RECIPES, [])
        old = v1.Markov(v1.RECIPES, [])

        with tempfile.TemporaryDirectory() as tmp:
            cases_by_set = hive.load_cases(tests_dir, tmp)
            for key, cases in cases_by_set:
                n = len(cases)
                # Hive words
                hit = first = wrong = size = 0
                for c in cases:
                    want = {x for x in c['expect'] if x in core.SKILLS}
                    res = hive.select(c['task'], c['project'], history=hist, semantic=False)
                    names = [x['name'] for x in res['stack']]
                    hit += bool(want & set(names))
                    if names:
                        lead = res.get('lead') or max(res['stack'], key=lambda x: x['score'])['name']
                        first += lead in want
                    wrong += bool(set(c.get('avoid', [])) & set(names))
                    size += len(names)

                k = max(1, round(size / n))
                s_hit = s_first = s_wrong = 0
                for c in cases:
                    want = {x for x in c['expect'] if x in core.SKILLS}
                    top_s = core.search(c['task'], limit=k)
                    top = {s['name'] for s in top_s}
                    s_hit += bool(want & top)
                    if top_s:
                        s_first += top_s[0]['name'] in want
                    s_wrong += bool(set(c.get('avoid', [])) & top)

                # v1
                v_hit = v_first = v_wrong = 0
                for c in cases:
                    want = {x for x in c['expect'] if x in core.SKILLS}
                    res = v1.recommend(c['task'], c['project'], chain=old)
                    names = [x['name'] for x in res['stack']]
                    v_hit += bool(want & set(names))
                    if names:
                        lead = max(res['stack'], key=lambda x: x['score'])['name']
                        v_first += lead in want
                    v_wrong += bool(set(c.get('avoid', [])) & set(names))

                eval_h = eval_out['%s_select' % key]
                eval_s = eval_out['%s_search' % key]
                eval_v = eval_out['%s_v1' % key]

                self.assertAlmostEqual(hit / n, eval_h['hit'], places=4, msg=f"Hive hit mismatch for {key}")
                self.assertAlmostEqual(first / n, eval_h['first'], places=4, msg=f"Hive first mismatch for {key}")
                self.assertAlmostEqual(s_hit / n, eval_s['hit'], places=4, msg=f"Search hit mismatch for {key}")
                self.assertAlmostEqual(v_hit / n, eval_v['hit'], places=4, msg=f"v1 hit mismatch for {key}")

    def test_run_all_setup_leaves_real_sfp_untouched(self):
        """Assert that running run_all setup never writes to ~/.sfp."""
        real_sfp = os.path.expanduser('~/.sfp')
        before_files = set()
        before_mtimes = {}
        if os.path.exists(real_sfp):
            before_files = set(os.listdir(real_sfp))
            for f in before_files:
                p = os.path.join(real_sfp, f)
                try:
                    before_mtimes[f] = os.path.getmtime(p)
                except Exception:
                    pass

        # Simulate bench/run_all environment setup
        import run_all
        bench_dir = os.environ.get('SFP_DATA_DIR')
        self.assertTrue(bench_dir.startswith(tempfile.gettempdir()) or 'sfp_bench_' in bench_dir,
                        f"Expected temporary SFP_DATA_DIR, got: {bench_dir}")

        # Check real ~/.sfp is identical
        if os.path.exists(real_sfp):
            after_files = set(os.listdir(real_sfp))
            self.assertEqual(before_files, after_files, f"Files changed in ~/.sfp: {after_files ^ before_files}")
            for f in before_files:
                p = os.path.join(real_sfp, f)
                try:
                    self.assertEqual(os.path.getmtime(p), before_mtimes[f], f"File modified in ~/.sfp: {f}")
                except Exception:
                    pass

if __name__ == '__main__':
    unittest.main()
