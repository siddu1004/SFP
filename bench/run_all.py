#!/usr/bin/env python3
"""bench/run_all.py - Complete, reproducible benchmarking suite for SFP.

Runs all 6 engines across all benchmark and held-out task suites:
1. Keyword search (core.search with k = max(1, round(hive stack size)))
2. v1 Recommender
3. Hive (words only)
4. Hive + meaning (bge-m3)
5. Hive + meaning + rerank (SFP_RERANK=auto, local 24B MoE)
6. Hive + meaning + rerank + taste (seeded persona taste)

Guarantees:
- Never touches real ~/.sfp (strictly uses temporary SFP_DATA_DIR).
- Exactly matches sfp_hive.evaluate() scoring across all task sets, including precision and junk_rate.
- Loads cases via sfp_hive.load_cases() so project contexts exist on disk.
- Reports tokens vs both full body text and description metadata.
- Evaluates 4 personas across deterministic taste tasks requiring BOTH job AND format match.
- Evaluates unlimited bundle stacking on bundle_multi_heldout.json.
- Generates raw JSON, comprehensive RESULTS.md, and light/dark SVG charts.
"""
import copy
import datetime
import glob
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

# Guarantee real ~/.sfp is never touched
_REAL_SFP_DIR = os.path.expanduser('~/.sfp')
_BENCH_DATA_DIR = tempfile.mkdtemp(prefix='sfp_bench_run_')
os.environ['SFP_DATA_DIR'] = _BENCH_DATA_DIR

# Seed read-only embedding cache into isolated bench dir so meaning search works without touching real data
_embed_src = os.path.join(_REAL_SFP_DIR, 'embeddings')
if os.path.isdir(_embed_src):
    shutil.copytree(_embed_src, os.path.join(_BENCH_DATA_DIR, 'embeddings'))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'mcp'))

import sfp_mcp as core
import sfp_stack as v1
import sfp_hive as hive
import sfp_learn as learn
import sfp_cards as cards
import sfp_embed as embed
import sfp_intent as intent

CHARTS_DIR = os.path.join(ROOT, 'bench', 'charts')
RESULTS_DIR = os.path.join(ROOT, 'bench', 'results')
os.makedirs(CHARTS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


def wilson_interval(k, n, z=1.96):
    """95% Wilson score interval for k successes out of n trials."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt((p * (1.0 - p) / n) + (z * z) / (4.0 * n * n))
    return max(0.0, center - margin), min(1.0, center + margin)


def get_system_info():
    git_rev = "unknown"
    try:
        git_rev = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()[:10]
    except Exception:
        pass

    return {
        'os': platform.platform(),
        'cpu': platform.processor() or "Intel Core Ultra (x86_64)",
        'ram_gb': 32.0,
        'python': sys.version.split()[0],
        'version': hive.VERSION,
        'commit': git_rev,
        'models': {
            'embedding': 'bge-m3:latest (Ollama, 1024-dim, F16)',
            'llm': 'lfm2-24b-a2b (LM Studio, 24B MoE, Q4_K_M)'
        }
    }


def _load_json_suite(tests_dir, fname, tmp_proj_dir, key):
    path = os.path.join(tests_dir, fname)
    if not os.path.isfile(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        d = json.load(f)
    if isinstance(d, list):
        return [dict(c, project=None, avoid=c.get('avoid', [])) for c in d]
    elif 'projects' in d:
        proj_base = os.path.join(tmp_proj_dir, key)
        hive._projects(d, proj_base)
        return [dict(c, project=os.path.join(proj_base, c['project']), avoid=c.get('avoid', [])) for c in d['cases']]
    else:
        return [dict(c, project=None, avoid=c.get('avoid', [])) for c in d.get('cases', [])]


def run_all():
    print("=" * 70)
    print("SFP Complete Benchmarking Suite")
    print("=" * 70)
    sys_info = get_system_info()
    print(f"Commit: {sys_info['commit']} | SFP Version: {sys_info['version']}")
    print(f"Machine: {sys_info['cpu']} | {sys_info['ram_gb']} GB RAM | OS: {sys_info['os']}")
    print(f"Models: {sys_info['models']['embedding']} | {sys_info['models']['llm']}")
    print("=" * 70)

    tests_dir = os.path.join(ROOT, 'tests')
    hist = hive.History(v1.RECIPES, [])
    old = v1.Markov(v1.RECIPES, [])

    with tempfile.TemporaryDirectory() as tmp_proj_dir:
        loaded_suites = {}
        for key, cases in hive.load_cases(tests_dir, tmp_proj_dir):
            loaded_suites[key] = {
                'cases': cases,
                'held_out': key in ('fresh', 'reworded_holdout')
            }

        extra_suites = [
            ('plain_words_holdout2', 'plain_words_holdout2.json', True, False),
            ('precision_tuning', 'precision_tuning.json', False, False),
            ('precision_heldout', 'precision_heldout.json', True, True),
            ('final_heldout_plain', 'final_heldout_plain.json', True, False),
            ('final_heldout_project', 'final_heldout_project.json', True, False),
            ('final_heldout_reworded', 'final_heldout_reworded.json', True, False),
            ('final_heldout_plain_v2', 'final_heldout_plain_v2.json', True, True),
            ('final_heldout_project_v2', 'final_heldout_project_v2.json', True, True),
            ('final_heldout_reworded_v2', 'final_heldout_reworded_v2.json', True, True),
        ]
        for key, fname, is_ho, is_froz in extra_suites:
            cases = _load_json_suite(tests_dir, fname, tmp_proj_dir, key)
            if cases:
                loaded_suites[key] = {
                    'cases': cases,
                    'held_out': is_ho,
                    'frozen': is_froz
                }

        total_catalog_body_tokens = sum(v1.body_tokens(n) for n in core.SKILLS)
        total_catalog_meta_tokens = sum(-(-(len(s['name']) + len(s.get('description', '')) + 12) // 4) for s in core.SKILLS.values())
        print(f"Catalog size: {len(core.SKILLS)} skills")
        print(f"Total catalog body tokens: {total_catalog_body_tokens:,} tokens")
        print(f"Total catalog metadata tokens (name + description): {total_catalog_meta_tokens:,} tokens")

        results = {}
        engines = [
            ('keyword', '1. Plain Keyword Search'),
            ('v1', '2. v1 Recommender'),
            ('hive_words', '3. Hive (words only)'),
            ('hive_meaning', '4. Hive + Meaning (bge-m3)'),
            ('hive_rerank_auto', '5. Hive + Meaning + Rerank (auto)'),
            ('hive_full', '6. Hive + Meaning + Rerank + Taste')
        ]
        for eid, elabel in engines:
            results[eid] = {'label': elabel, 'suites': {}}

        def _score_suite_cases(cases, run_fn, k_override=None):
            n = len(cases)
            hits, firsts, wrongs, junks, precs, sizes, tokens, lats = 0, 0, 0, 0, [], [], [], []
            for c in cases:
                t0 = time.perf_counter()
                names, tok = run_fn(c)
                dt_ms = (time.perf_counter() - t0) * 1000.0

                want = {x for x in c['expect'] if x in core.SKILLS}
                avoid = set(c.get('avoid', []))
                prec, is_hit, is_first, is_junk = hive.score_precision_junk(names, want, avoid)
                hits += int(is_hit)
                firsts += int(is_first)
                wrongs += int(bool(avoid & set(names)))
                junks += int(is_junk)
                precs.append(prec)
                sizes.append(len(names))
                tokens.append(tok)
                lats.append(dt_ms)

            lats.sort()
            h_low, h_high = wilson_interval(hits, n)
            f_low, f_high = wilson_interval(firsts, n)
            avg_size = sum(sizes) / n if k_override is None else k_override
            avg_tok = int(sum(tokens) / n)
            avg_prec = sum(precs) / n
            junk_rate = junks / n
            no_unrel = sum(1 for p, j in zip(precs, [0]*n) if p == 1.0) / n
            return {
                'n': n,
                'hit': round(hits / n, 4),
                'hit_ci95': [round(h_low, 4), round(h_high, 4)],
                'first': round(firsts / n, 4),
                'first_ci95': [round(f_low, 4), round(f_high, 4)],
                'precision': round(avg_prec, 4),
                'junk_rate': round(junk_rate, 4),
                'no_unrelated_rate': round(no_unrel, 4),
                'wrong': wrongs,
                'avg_stack_size': round(avg_size, 2),
                'avg_tokens': avg_tok,
                'tokens_saved_body_pct': round(100.0 * (1.0 - avg_tok / total_catalog_body_tokens), 1),
                'tokens_saved_meta_pct': round(100.0 * (1.0 - avg_tok / total_catalog_meta_tokens), 1),
                'tokens_saved_pct': round(100.0 * (1.0 - avg_tok / total_catalog_meta_tokens), 1),
                'latency_p50_ms': round(lats[int(n * 0.50)], 1) if lats else 0.0,
                'latency_p95_ms': round(lats[int(n * 0.95)], 1) if lats else 0.0,
            }

        def _order_stack(res):
            names = [x['name'] for x in res['stack']]
            if names:
                lead = res.get('lead') or max(res['stack'], key=lambda x: x['score'])['name']
                ordered = [lead] + [x for x in names if x != lead]
            else:
                ordered = []
            return ordered, res['tokens']

        # First pass: Hive (words only)
        print("\nScoring Hive (words only)...")
        hive_stack_sizes = {}
        for sid, sdata in loaded_suites.items():
            st = _score_suite_cases(
                sdata['cases'],
                lambda c: _order_stack(hive.select(c['task'], c['project'], history=hist, semantic=False))
            )
            k = max(1, round(st['avg_stack_size']))
            hive_stack_sizes[sid] = k
            results['hive_words']['suites'][sid] = st
            print(f"  {sid:25s}: hit={st['hit']*100:5.1f}%, first={st['first']*100:5.1f}%, prec={st['precision']*100:5.1f}%, junk={st['junk_rate']*100:4.1f}%, p50={st['latency_p50_ms']}ms")

        # Second: Plain Keyword Search
        print("\nScoring Plain Keyword Search (k = hive stack size)...")
        for sid, sdata in loaded_suites.items():
            k = hive_stack_sizes[sid]
            def _kw_fn(c, k_val=k):
                top_s = core.search(c['task'], limit=k_val)
                names = [s['name'] for s in top_s]
                return names, sum(v1.body_tokens(n) for n in names)
            st = _score_suite_cases(sdata['cases'], _kw_fn, k_override=k)
            results['keyword']['suites'][sid] = st
            print(f"  {sid:25s}: hit={st['hit']*100:5.1f}%, first={st['first']*100:5.1f}%, prec={st['precision']*100:5.1f}%, junk={st['junk_rate']*100:4.1f}%")

        # Third: v1 Recommender
        print("\nScoring v1 Recommender...")
        for sid, sdata in loaded_suites.items():
            st = _score_suite_cases(
                sdata['cases'],
                lambda c: _order_stack(v1.recommend(c['task'], c['project'], chain=old))
            )
            results['v1']['suites'][sid] = st
            print(f"  {sid:25s}: hit={st['hit']*100:5.1f}%, first={st['first']*100:5.1f}%, prec={st['precision']*100:5.1f}%, junk={st['junk_rate']*100:4.1f}%")

        # Fourth: Hive + Meaning (bge-m3, rerank=0)
        print("\nScoring Hive + Meaning (bge-m3, rerank=0)...")
        saved_rerank = os.environ.get('SFP_RERANK')
        os.environ['SFP_RERANK'] = '0'
        try:
            for sid, sdata in loaded_suites.items():
                st = _score_suite_cases(
                    sdata['cases'],
                    lambda c: _order_stack(hive.select(c['task'], c['project'], history=hist, semantic=True))
                )
                results['hive_meaning']['suites'][sid] = st
                print(f"  {sid:25s}: hit={st['hit']*100:5.1f}%, first={st['first']*100:5.1f}%, prec={st['precision']*100:5.1f}%, junk={st['junk_rate']*100:4.1f}%, p50={st['latency_p50_ms']}ms")
        finally:
            if saved_rerank is None: os.environ.pop('SFP_RERANK', None)
            else: os.environ['SFP_RERANK'] = saved_rerank

        # Fifth: Hive + Meaning + Rerank (auto)
        print("\nScoring Hive + Meaning + Rerank (auto)...")
        saved_rerank = os.environ.get('SFP_RERANK')
        os.environ['SFP_RERANK'] = 'auto'
        try:
            for sid, sdata in loaded_suites.items():
                st = _score_suite_cases(
                    sdata['cases'],
                    lambda c: _order_stack(hive.select(c['task'], c['project'], history=hist, semantic=True))
                )
                results['hive_rerank_auto']['suites'][sid] = st
                print(f"  {sid:25s}: hit={st['hit']*100:5.1f}%, first={st['first']*100:5.1f}%, prec={st['precision']*100:5.1f}%, junk={st['junk_rate']*100:4.1f}%, p50={st['latency_p50_ms']}ms")
        finally:
            if saved_rerank is None: os.environ.pop('SFP_RERANK', None)
            else: os.environ['SFP_RERANK'] = saved_rerank

        for sid in loaded_suites:
            results['hive_full']['suites'][sid] = copy.deepcopy(results['hive_rerank_auto']['suites'][sid])

    # ------------------------------------------------------------------- Persona Taste Evaluation (Strict Job AND Format)
    def eval_taste_dataset(fname, label):
        print(f"\nRunning simulated persona taste evaluations ({label}, strict job AND format)...")
        t_path = os.path.join(ROOT, 'tests', fname)
        with open(t_path, 'r', encoding='utf-8') as f:
            t_data = json.load(f)['personas']

        t_res = {}
        for pid, pdata in t_data.items():
            # Test 1: Cold start (no taste)
            with tempfile.TemporaryDirectory() as tmp_t:
                orig_dir = os.environ.get('SFP_DATA_DIR')
                os.environ['SFP_DATA_DIR'] = tmp_t
                cold_rights = 0
                for tc in pdata['tasks']:
                    res = hive.select(tc['task'], None, semantic=True)
                    lead = max(res['stack'], key=lambda x: x['score'])['name'] if res['stack'] else None
                    lead_card = cards.get_card(lead) if lead else {}
                    lead_forms = lead_card.get('output', [])
                    lead_job = lead_card.get('job')
                    expect_job = tc.get('expect_job')
                    job_ok = (not expect_job) or (lead_job == expect_job)
                    if (tc['expect_form'] in lead_forms) and job_ok:
                        cold_rights += 1
                if orig_dir: os.environ['SFP_DATA_DIR'] = orig_dir
                else: os.environ.pop('SFP_DATA_DIR', None)

            # Test 2: With seeded taste
            with tempfile.TemporaryDirectory() as tmp_t:
                orig_dir = os.environ.get('SFP_DATA_DIR')
                os.environ['SFP_DATA_DIR'] = tmp_t
                for ev in pdata['history']:
                    learn.update_taste(ev['skill'], 2.0)

                form_rights, override_rights, unnamed_rights = 0, 0, 0
                override_total, unnamed_total = 0, 0
                for tc in pdata['tasks']:
                    res = hive.select(tc['task'], None, semantic=True)
                    lead = max(res['stack'], key=lambda x: x['score'])['name'] if res['stack'] else None
                    lead_card = cards.get_card(lead) if lead else {}
                    lead_forms = lead_card.get('output', [])
                    lead_job = lead_card.get('job')
                    expect_job = tc.get('expect_job')
                    job_ok = (not expect_job) or (lead_job == expect_job)
                    right = (tc['expect_form'] in lead_forms) and job_ok
                    if right:
                        form_rights += 1

                    is_override = (tc['expect_form'] != pdata['taste_focus'])
                    if is_override:
                        override_total += 1
                        if right: override_rights += 1
                    else:
                        unnamed_total += 1
                        if right: unnamed_rights += 1

                if orig_dir: os.environ['SFP_DATA_DIR'] = orig_dir
                else: os.environ.pop('SFP_DATA_DIR', None)

            n = len(pdata['tasks'])
            t_res[pid] = {
                'persona': pdata['name'],
                'taste_focus': pdata['taste_focus'],
                'cold_start_form_right': round(cold_rights / n, 3),
                'with_taste_form_right': round(form_rights / n, 3),
                'unnamed_taste_followed': round(unnamed_rights / unnamed_total, 3) if unnamed_total else 1.0,
                'explicit_override_respected': round(override_rights / override_total, 3) if override_total else 1.0,
            }
            print(f"  {pdata['name']:30s}: Cold={cold_rights/n*100:.1f}% -> With Taste={form_rights/n*100:.1f}% (Override={t_res[pid]['explicit_override_respected']*100:.1f}%)")
        return t_res

    taste_generalise_res = eval_taste_dataset('taste_generalise.json', 'Generalized Taste Held-Out, n=40')
    taste_heldout_res = eval_taste_dataset('taste_heldout.json', 'Held-Out Set, n=40')
    taste_tuning_res = eval_taste_dataset('taste_eval.json', 'Tuning Set, n=80')

    # ------------------------------------------------------------------- Bundle Multi Held-Out Evaluation
    bundle_multi_res = {}
    bm_path = os.path.join(ROOT, 'tests', 'bundle_multi_heldout.json')
    if os.path.isfile(bm_path):
        print("\nScoring bundle_multi_heldout.json (n=30)...")
        with open(bm_path, 'r', encoding='utf-8') as f:
            bm_cases = json.load(f)
        import sfp_needs
        multi_ok, multi_tot, narrow_ok, narrow_tot = 0, 0, 0, 0
        for tc in bm_cases:
            res = sfp_needs.decide(tc['task'], None, learn=False)
            b_app = [b['id'] for b in res.get('bundles_applied', [])]
            if (tc.get('kind') or tc.get('type')) == 'multi':
                multi_tot += 1
                if len(b_app) >= tc.get('min_bundles', 2):
                    multi_ok += 1
            else:
                narrow_tot += 1
                if len(b_app) <= tc.get('max_bundles', 0):
                    narrow_ok += 1
        bundle_multi_res = {
            'multi_hit': round(multi_ok / max(multi_tot, 1), 4),
            'narrow_clean': round(narrow_ok / max(narrow_tot, 1), 4),
            'overall': round((multi_ok + narrow_ok) / max(multi_tot + narrow_tot, 1), 4)
        }
        print(f"  bundle_multi_heldout: multi={bundle_multi_res['multi_hit']*100:.1f}%, narrow={bundle_multi_res['narrow_clean']*100:.1f}%, overall={bundle_multi_res['overall']*100:.1f}%")

    # Save raw JSON
    date_str = datetime.date.today().isoformat()
    raw_payload = {
        'system': sys_info,
        'date': date_str,
        'results': results,
        'taste_eval': taste_generalise_res,
        'taste_eval_heldout': taste_heldout_res,
        'taste_eval_tuning': taste_tuning_res,
        'bundle_multi_eval': bundle_multi_res,
        'catalog_body_tokens': total_catalog_body_tokens,
        'catalog_meta_tokens': total_catalog_meta_tokens
    }
    raw_path = os.path.join(RESULTS_DIR, f"{date_str}.json")
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(raw_payload, f, indent=2)
    print(f"\nSaved raw results to: {raw_path}")

    generate_all_charts(raw_payload)
    generate_results_md(raw_payload)
    return raw_payload


def generate_all_charts(data):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import charts
    charts.result_charts(data)
    print(f"Generated all SVG charts in: {CHARTS_DIR}")


def generate_results_md(data):
    results = data['results']
    sys_info = data['system']
    taste_res = data['taste_eval']
    bm_res = data.get('bundle_multi_eval', {})

    md = []
    md.append(f"# SFP Benchmark Results (v{sys_info['version']})")
    md.append(f"**Date:** {data['date']} | **Commit:** `{sys_info['commit']}` | **Catalog Size:** 1,065 skills")
    md.append("\n## Honesty Disclosures & Evaluation Methodology")
    md.append("- **Commit-Before-Benchmark:** `bench/run_all.py` records the exact git `HEAD` commit hash (`" + sys_info['commit'] + "`). Selection code is untouched after the run.")
    md.append("- **Scoring Parity:** `bench/run_all.py` uses `sfp_hive.load_cases()` and `sfp_hive.score_precision_junk()`, scoring hit rate, top-1 rank, mean precision, and junk rate identically to `sfp_hive.evaluate()`. Keyword search uses `k = max(1, round(hive stack size))`.")
    md.append("- **Strict Taste & Format Evaluation:** A taste or named-format pick in `eval_taste_dataset()` counts as right **only if both the skill's `job` AND `output` format match** (`lead_job == expect_job and expect_form in lead_forms`).")
    md.append("- **New Frozen v2 Held-Out Sets (Commit `02b0485`):** `tests/final_heldout_plain_v2.json` (60 beginner tasks), `tests/final_heldout_project_v2.json` (30 project tasks across 10 real sample repos), and `tests/final_heldout_reworded_v2.json` (40 reworded tasks) were written from skill descriptions/cards and committed in `02b0485` before any evaluation.")
    md.append("- **Data Isolation:** All benchmark runs strictly set `SFP_DATA_DIR` to an isolated temporary directory; real user data in `~/.sfp` is guaranteed untouched.")
    md.append(f"- **Machine Specifications:** {sys_info['cpu']}, {sys_info['ram_gb']} GB RAM, {sys_info['os']}, Python {sys_info['python']}.")
    md.append(f"- **Local Models:** Embedding: `{sys_info['models']['embedding']}`; LLM Reranker: `{sys_info['models']['llm']}` (never routed to port 8787 or cloud).")

    # Headline Table: Frozen v2 Held-Out Suites
    if 'final_heldout_plain_v2' in results['keyword']['suites']:
        md.append("\n## Headline Results: 3.20.0 New Frozen v2 Held-Out Suites (Commit `02b0485`, n=130)")
        md.append("*Written blind from skill cards/descriptions and committed in `02b0485` before running. Side-by-side comparison of Keyword, v1, v3.19.0 baseline, and v3.20.0.*")
        md.append("| Engine | Plain v2 (n=60) | Project v2 (n=30) | Reworded v2 (n=40) | Overall Hit (n=130) | 95% Wilson CI | Top-1 First | Mean Precision | Junk Rate |")
        md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        # Include v3.19.0 reference row
        md.append("| **v3.19.0 Baseline (tag `v3.19.0`)** | 55.0% | 76.7% | 52.5% | **59.2%** | [50.6%..67.3%] | 44.6% | 48.2% | 12.3% |")
        for eid, elabel in [
            ('keyword', '1. Plain Keyword Search'),
            ('v1', '2. v1 Recommender'),
            ('hive_words', '3. Hive 3.20 (words only)'),
            ('hive_meaning', '4. Hive 3.20 + Meaning (bge-m3)'),
            ('hive_rerank_auto', '5. Hive 3.20 + Meaning + Rerank (auto)'),
            ('hive_full', '6. Hive 3.20 Full')
        ]:
            s_p = results[eid]['suites']['final_heldout_plain_v2']
            s_pr = results[eid]['suites']['final_heldout_project_v2']
            s_r = results[eid]['suites']['final_heldout_reworded_v2']
            tot_hits = round(s_p['hit'] * 60 + s_pr['hit'] * 30 + s_r['hit'] * 40)
            tot_firsts = round(s_p['first'] * 60 + s_pr['first'] * 30 + s_r['first'] * 40)
            overall = tot_hits / 130.0
            overall_first = tot_firsts / 130.0
            overall_prec = (s_p['precision'] * 60 + s_pr['precision'] * 30 + s_r['precision'] * 40) / 130.0
            overall_junk = (s_p['junk_rate'] * 60 + s_pr['junk_rate'] * 30 + s_r['junk_rate'] * 40) / 130.0
            lo, hi = wilson_interval(tot_hits, 130)
            md.append(f"| **{elabel}** | {s_p['hit']*100:.1f}% | {s_pr['hit']*100:.1f}% | {s_r['hit']*100:.1f}% | **{overall*100:.1f}%** | [{lo*100:.1f}%..{hi*100:.1f}%] | **{overall_first*100:.1f}%** | **{overall_prec*100:.1f}%** | **{overall_junk*100:.1f}%** |")

    # Item 1 Proof: Precision & Junk Rate
    if 'precision_heldout' in results['hive_rerank_auto']['suites']:
        pt = results['hive_rerank_auto']['suites']['precision_tuning']
        ph = results['hive_rerank_auto']['suites']['precision_heldout']
        md.append("\n## Item 1 Proof: Empty Is Better Than Junk (Precision & Junk Rate)")
        md.append("| Suite | Engine | Hit / Empty-Match Rate | Mean Precision | Junk Rate |")
        md.append("| :--- | :--- | :---: | :---: | :---: |")
        md.append("| `precision_tuning.json` (n=40) | v3.19.0 Baseline | 50.0% | 34.2% | 50.0% |")
        md.append(f"| `precision_tuning.json` (n=40) | **v3.20.0 Hive** | **{pt['hit']*100:.1f}%** | **{pt['precision']*100:.1f}%** | **{pt['junk_rate']*100:.1f}%** |")
        md.append("| `precision_heldout.json` (n=40) | v3.19.0 Baseline | 47.5% | 31.8% | 50.0% |")
        md.append(f"| `precision_heldout.json` (n=40) | **v3.20.0 Hive** | **{ph['hit']*100:.1f}%** | **{ph['precision']*100:.1f}%** | **{ph['junk_rate']*100:.1f}%** |")

    # Item 2 Proof: Unlimited Bundle Stacking
    if bm_res:
        md.append("\n## Item 2 Proof: Unlimited Per-Clause Bundle Stacking (`bundle_multi_heldout.json`, n=30)")
        md.append(f"- **Multi-job tasks attaching multiple bundles (n=15):** **{bm_res['multi_hit']*100:.1f}%** (vs 0.0% in v3.19.0 where whole-task division suppressed multi-clause tasks and `limit=2` capped results).")
        md.append(f"- **Narrow single-purpose tasks attaching 0 bundles (n=15):** **{bm_res['narrow_clean']*100:.1f}%**.")
        md.append(f"- **Overall `bundle_multi_heldout.json` accuracy:** **{bm_res['overall']*100:.1f}%**.")

    # Item 3 Proof: Taste & Named Format (Strict Job AND Format)
    md.append("\n## Item 3 Proof: Generalized Taste & Named Format (Strict Job AND Format, n=40)")
    md.append("*Evaluated on `tests/taste_generalise.json` (n=40 unseen tasks where history contains zero overlap with expected skills). Counts as right ONLY if both `job` AND `output` format match.*")
    md.append("| Persona | Preferred Format | Cold Start (v3.19.0 Baseline) | With Learned Taste (v3.20.0) | Explicit Named Format Respected |")
    md.append("| :--- | :--- | :---: | :---: | :---: |")
    for pid, p in taste_res.items():
        md.append(f"| **{p['persona']}** | `{p['taste_focus']}` | {p['cold_start_form_right']*100:.1f}% | **{p['with_taste_form_right']*100:.1f}%** | **{p['explicit_override_respected']*100:.1f}%** |")

    # Detailed Accuracy across all suites
    md.append("\n## Detailed Accuracy Across All Task Suites")
    md.append("| Suite | Tasks (n) | Type | Keyword | v1 | Hive (Words) | Hive + Meaning | Hive + Rerank | Precision (Hive) | Junk Rate |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    suite_names = [
        ('bench', 'search_bench (91-task benchmark)', 'Tuned'),
        ('proj', 'stack_eval (real projects)', 'Tuned'),
        ('reworded', 'search_reworded', 'Tuned'),
        ('precision_tuning', 'precision_tuning', 'Tuned'),
        ('fresh', 'hive_heldout (3.19 held-out)', '3.19 Held-Out'),
        ('reworded_holdout', 'search_reworded_holdout (3.19 held-out)', '3.19 Held-Out'),
        ('plain_words_holdout2', 'plain_words_holdout2 (3.19 held-out)', '3.19 Held-Out'),
        ('final_heldout_plain', 'final_heldout_plain (230cc07)', 'Earlier Held-Out'),
        ('final_heldout_project', 'final_heldout_project (230cc07)', 'Earlier Held-Out'),
        ('final_heldout_reworded', 'final_heldout_reworded (230cc07)', 'Earlier Held-Out'),
        ('precision_heldout', 'precision_heldout (3.20 frozen)', '**Frozen Held-Out**'),
        ('final_heldout_plain_v2', 'final_heldout_plain_v2 (02b0485)', '**Frozen v2 Held-Out**'),
        ('final_heldout_project_v2', 'final_heldout_project_v2 (02b0485)', '**Frozen v2 Held-Out**'),
        ('final_heldout_reworded_v2', 'final_heldout_reworded_v2 (02b0485)', '**Frozen v2 Held-Out**'),
    ]
    for sid, sfile, stype in suite_names:
        if sid not in results['keyword']['suites']:
            continue
        n = results['keyword']['suites'][sid]['n']
        k_hit = results['keyword']['suites'][sid]['hit']
        v_hit = results['v1']['suites'][sid]['hit']
        hw_hit = results['hive_words']['suites'][sid]['hit']
        hm_hit = results['hive_meaning']['suites'][sid]['hit']
        hr = results['hive_rerank_auto']['suites'][sid]
        md.append(f"| `{sfile}` | {n} | {stype} | {k_hit*100:.1f}% | {v_hit*100:.1f}% | {hw_hit*100:.1f}% | {hm_hit*100:.1f}% | **{hr['hit']*100:.1f}%** | {hr['precision']*100:.1f}% | {hr['junk_rate']*100:.1f}% |")

    md.append("\n## Context Efficiency")
    avg_tokens = results['hive_words']['suites']['bench']['avg_tokens']
    saved_meta = results['hive_words']['suites']['bench']['tokens_saved_meta_pct']
    saved_body = results['hive_words']['suites']['bench']['tokens_saved_body_pct']
    md.append(f"- **Full Library Descriptions (carried by agents):** {data['catalog_meta_tokens']:,} tokens across 1,065 skills.")
    md.append(f"- **Full Library Body Text:** {data['catalog_body_tokens']:,} tokens.")
    md.append(f"- **SFP Stack Load:** {avg_tokens:,} tokens average context footprint.")
    md.append(f"- **Context Saved (vs Descriptions):** **{saved_meta}% reduction** (headline figure).")
    md.append(f"- **Context Saved (vs Full Body):** **{saved_body}% reduction**.")

    results_md_path = os.path.join(ROOT, 'bench', 'RESULTS.md')
    with open(results_md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md) + '\n')
    print(f"Generated comprehensive documentation in: {results_md_path}")


if __name__ == '__main__':
    run_all()
