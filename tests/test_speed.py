"""Speed work must not change any answer. These tests pin the fast paths to the plain definitions they replace.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import math
import os
import statistics
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['SFP_ROOT'] = ROOT
sys.path.insert(0, os.path.join(ROOT, 'mcp'))
import sfp_mcp as core  # noqa: E402
import sfp_stack as v1  # noqa: E402
import sfp_select as sel  # noqa: E402


def tasks():
    out = []
    for name in ('search_eval.json', 'search_holdout.json', 'search_fresh.json'):
        with open(os.path.join(ROOT, 'tests', name), encoding='utf-8') as f:
            out += [c['task'] for c in json.load(f)]
    return out


def brute_force_search(query, category=None, limit=10):
    """The search as first written: score every skill in the library."""
    words = list(dict.fromkeys(core.tokens(query)))
    if not words:
        return []
    n = len(core.INDEX)
    idf = {w: math.log(1 + n / (1 + core.DF.get(w, 0))) for w in words}
    hits = []
    for s, name, desc, cat in core.INDEX:
        if category and s['category'] != category:
            continue
        score, matched = 0.0, 0
        for w in words:
            part = 0.0
            if w in name:
                part += 3.0 * idf[w]
            if w in desc:
                part += idf[w] * (1 + min(0.5, 0.1 * (desc[w] - 1)))
            if w in cat:
                part += 0.4 * idf[w]
            if part:
                matched += 1
                score += part
        if score:
            score *= 0.4 + 0.6 * matched / len(words)
            if set(words) == name:
                score *= 1.5
            hits.append((score, s))
    hits.sort(key=lambda h: (-h[0], h[1]['name']))
    return hits[:max(1, limit)]


class IndexCacheTest(unittest.TestCase):
    def test_saved_index_matches_a_fresh_build(self):
        self.assertTrue(os.path.isfile(core.INDEX_FILE), 'run python3 scripts/sync.py to write index.json')
        with open(core.INDEX_FILE, encoding='utf-8') as f:
            self.assertEqual(json.load(f)['key'], core.index_key(), 'index.json is stale: run python3 scripts/sync.py')
        docs, df = core.build_index()
        self.assertEqual(df, core.DF)
        self.assertEqual([(s['name'], n, d, c) for s, n, d, c in docs],
                         [(s['name'], n, d, c) for s, n, d, c in core.INDEX])

    def test_a_stale_or_broken_index_is_rebuilt_not_trusted(self):
        fresh = core.build_index()
        original = core.INDEX_FILE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                core.INDEX_FILE = os.path.join(tmp, 'index.json')
                self.assertEqual(core.load_index()[1], fresh[1])          # missing file
                with open(core.INDEX_FILE, 'w') as f:
                    f.write('{not json')
                self.assertEqual(core.load_index()[1], fresh[1])          # broken file
                with open(core.INDEX_FILE, 'w') as f:
                    json.dump({'key': {'catalog': 'x', 'tokenizer': 'y'}, 'df': {'bogus': 1}, 'skills': []}, f)
                self.assertEqual(core.load_index()[1], fresh[1])          # made from another catalog
        finally:
            core.INDEX_FILE = original


class SearchEquivalenceTest(unittest.TestCase):
    def test_lookup_search_equals_scoring_every_skill(self):
        queries = tasks() + ['c++ unit tests', 'the of a', 'postgres', 'accessibility audit for a dark theme', 'zzzz qqqq']
        for q in queries:
            for category in (None, 'frontend', 'security'):
                got = core.scored_search(q, category, 50)
                want = brute_force_search(q, category, 50)
                self.assertEqual([(round(s, 9), x['name']) for s, x in got], [(round(s, 9), x['name']) for s, x in want], q)


class StackEquivalenceTest(unittest.TestCase):
    def test_main_phase_cache_matches_the_definition(self):
        for name in core.SKILLS:
            self.assertEqual(v1.main_phase(name), v1._main_phase(name), name)

    def test_phase_vectors_match_the_original_formula(self):
        for s, name, desc, _ in core.INDEX:
            for p, lex in v1.PHASE_LEX.items():
                want = 2.0 * len(name & lex) + sum(c for w, c in desc.items() if w in lex)
                self.assertEqual(v1.SKILL_PHASE[s['name']].get(p, 0), want, (s['name'], p))

    def test_predictions_match_scoring_every_pair(self):
        now = time.time()
        events = [{'t': now, 'skill': 'golang-testing', 'session': 'a'}, {'t': now, 'skill': 'canary-watch', 'session': 'a'},
                  {'t': now, 'skill': 'golang-testing', 'session': 'b'}, {'t': now, 'skill': 'docker-patterns', 'session': 'b'}]
        for col in (v1.Markov(v1.RECIPES, []), sel.History(v1.RECIPES, events, now=now)):
            for a in ('api-design', 'golang-testing', 'career-ops', 'swiftui-patterns'):
                for exclude in ((), {'database-migrations', 'canary-watch'}):
                    want = sorted(((col.prob(a, b), b) for b in core.SKILLS
                                   if b != a and b not in exclude and b not in ('sfp', 'sfp-select')),
                                  key=lambda x: (-x[0], x[1]))[:7]
                    got = col.next(a, 7, exclude)
                    self.assertEqual([b for _, b in got], [b for _, b in want], (a, exclude))
                    for (p, _), (q, _) in zip(got, want):
                        self.assertAlmostEqual(p, q, places=12)

    def test_project_scan_prefilter_loses_nothing(self):
        """Every kind of file the scan knows about is still found when it sits among many it does not."""
        with tempfile.TemporaryDirectory() as tmp:
            files = {'package.json': '{"dependencies": {"next": "1"}}', 'requirements.txt': 'django\n', 'go.mod': 'module x',
                     'Cargo.toml': '', 'pom.xml': 'spring-boot', 'pubspec.yaml': 'flutter', 'Gemfile': 'rails',
                     'composer.json': 'laravel', 'Package.swift': '', 'Dockerfile.dev': '', 'schema.prisma': '',
                     'angular.json': '', 'vite.config.ts': '', 'playwright.config.ts': '', 'conftest.py': '',
                     'Shop.csproj': '', 'app.py': '', 'main.rs': ''}
            for n, body in files.items():
                with open(os.path.join(tmp, n), 'w') as f:
                    f.write(body)
            for i in range(300):  # files the scan ignores
                with open(os.path.join(tmp, 'notes%d.md' % i), 'w') as f:
                    f.write('x')
            terms = v1.scan_project(tmp)['terms']
            for want in ('nextj', 'django', 'golang', 'rust', 'springboot', 'flutter', 'rails', 'laravel', 'swift', 'docker',
                         'prisma', 'angular', 'vite', 'playwright', 'pytest', 'dotnet', 'python'):
                self.assertIn(v1._one(want), terms, sorted(terms))  # terms are stored stemmed (rails -> rail)


class SpeedBudgetTest(unittest.TestCase):
    """Generous budgets, about ten times what a laptop needs, so only a real regression fails them."""

    @classmethod
    def setUpClass(cls):
        cls.col = sel.History(v1.RECIPES, [])
        cls.scan = v1.scan_project(os.path.join(ROOT, 'tests'))

    def median_ms(self, fn, runs=15):
        fn()
        times = []
        for _ in range(runs):
            t = time.perf_counter()
            fn()
            times.append((time.perf_counter() - t) * 1000)
        return statistics.median(times)

    def test_a_decision_is_fast(self):
        ms = self.median_ms(lambda: sel.select('write tests for the order view', history=self.col, scan_result=self.scan))
        self.assertLess(ms, 40, 'median %.1f ms' % ms)

    def test_a_search_is_fast(self):
        ms = self.median_ms(lambda: core.search('add a postgres migration without downtime'))
        self.assertLess(ms, 10, 'median %.1f ms' % ms)

    def test_a_prediction_is_fast(self):
        ms = self.median_ms(lambda: self.col.next('api-design', 5))
        self.assertLess(ms, 20, 'median %.1f ms' % ms)

    def test_scanning_a_project_is_fast(self):
        ms = self.median_ms(lambda: v1.scan_project(ROOT), runs=5)
        self.assertLess(ms, 800, 'median %.1f ms' % ms)


if __name__ == '__main__':
    unittest.main()
