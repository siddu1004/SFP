# SFP Benchmark Results (v3.20.0)
**Date:** 2026-11-05 | **Commit:** `c6240b1` (selection code identical to `d73ac604db`) | **Catalog Size:** 1,065 skills

## Honesty Disclosures & Evaluation Methodology
- **Commit-Before-Benchmark:** `bench/run_all.py` recorded commit `d73ac604db` (`c6240b1` is the doc-only sync commit). Selection code is untouched after the run.
- **Scoring Parity:** `bench/run_all.py` uses `sfp_hive.load_cases()` and `sfp_hive.score_precision_junk()`, scoring hit rate, top-1 rank, mean precision, and junk rate identically to `sfp_hive.evaluate()`. Keyword search uses `k = max(1, round(hive stack size))`.
- **Strict Taste & Format Evaluation:** A taste or named-format pick in `eval_taste_dataset()` counts as right **only if both the skill's `job` AND `output` format match** (`lead_job == expect_job and expect_form in lead_forms`).
- **New Frozen v2 Held-Out Sets (Commit `02b0485`):** `tests/final_heldout_plain_v2.json` (60 beginner tasks), `tests/final_heldout_project_v2.json` (30 project tasks across 10 real sample repos), and `tests/final_heldout_reworded_v2.json` (40 reworded tasks) were written from skill descriptions/cards and committed in `02b0485` before any evaluation.
- **Data Isolation:** All benchmark runs strictly set `SFP_DATA_DIR` to an isolated temporary directory; real user data in `~/.sfp` is guaranteed untouched.
- **Machine Specifications:** Intel64 Family 6 Model 197 Stepping 2, GenuineIntel, 32.0 GB RAM, Windows-11-10.0.26300-SP0, Python 3.13.14.
- **Local Models:** Embedding: `bge-m3:latest (Ollama, 1024-dim, F16)`; LLM Reranker: `lfm2-24b-a2b (LM Studio, 24B MoE, Q4_K_M)` (never routed to port 8787 or cloud).

## Headline Results: 3.20.0 New Frozen v2 Held-Out Suites (Commit `02b0485`, n=130)
*Written blind from skill cards/descriptions and committed in `02b0485` before running. Side-by-side comparison of Keyword, v1, v3.19.0 baseline, and v3.20.0.*
| Engine | Plain v2 (n=60) | Project v2 (n=30) | Reworded v2 (n=40) | Overall Hit (n=130) | 95% Wilson CI | Top-1 First | Mean Precision | Junk Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **v3.19.0 Baseline (tag `v3.19.0`)** | 55.0% | 76.7% | 52.5% | **59.2%** | [50.6%..67.3%] | 44.6% | 48.2% | 12.3% |
| **1. Plain Keyword Search** | 100.0% | 90.0% | 100.0% | **97.7%** | [93.4%..99.2%] | **97.7%** | **97.7%** | **0.0%** |
| **2. v1 Recommender** | 98.3% | 93.3% | 100.0% | **97.7%** | [93.4%..99.2%] | **97.7%** | **90.3%** | **0.0%** |
| **3. Hive 3.20 (words only)** | 95.0% | 96.7% | 92.5% | **94.6%** | [89.3%..97.4%] | **94.6%** | **85.9%** | **0.0%** |
| **4. Hive 3.20 + Meaning (bge-m3)** | 98.3% | 96.7% | 95.0% | **96.9%** | [92.4%..98.8%] | **95.4%** | **82.4%** | **0.0%** |
| **5. Hive 3.20 + Meaning + Rerank (auto)** | 98.3% | 96.7% | 95.0% | **96.9%** | [92.4%..98.8%] | **94.6%** | **81.7%** | **0.0%** |
| **6. Hive 3.20 Full** | 98.3% | 96.7% | 95.0% | **96.9%** | [92.4%..98.8%] | **94.6%** | **81.7%** | **0.0%** |

## Item 1 Proof: Empty Is Better Than Junk (Precision & Junk Rate)
| Suite | Engine | Hit / Empty-Match Rate | Mean Precision | Junk Rate |
| :--- | :--- | :---: | :---: | :---: |
| `precision_tuning.json` (n=40) | v3.19.0 Baseline | 50.0% | 34.2% | 50.0% |
| `precision_tuning.json` (n=40) | **v3.20.0 Hive** | **100.0%** | **86.9%** | **0.0%** |
| `precision_heldout.json` (n=40) | v3.19.0 Baseline | 47.5% | 31.8% | 50.0% |
| `precision_heldout.json` (n=40) | **v3.20.0 Hive** | **87.5%** | **76.5% (79.8% words-only)** | **0.0%** |

## Item 2 Proof: Unlimited Per-Clause Bundle Stacking (`bundle_multi_heldout.json`, n=30)
- **Multi-job tasks attaching $\ge 2$ bundles via `sfp_needs.decide` (n=15):** **26.7%** (4/15 attach 2–5 bundles; 46.7% attach $\ge 1$ bundle, vs 0.0% in v3.19.0 where whole-task division suppressed multi-clause tasks and `limit=2` capped results).
- **Narrow single-purpose tasks attaching 0 bundles (n=15):** **100.0%** (15/15 attach 0 bundles).
- **Named `--use-bundles` stacking (2, 4, and 10 bundles):** **100.0%** (all attach with zero duplicate skills and full `tokens_used` / `budget_omitted` reporting).
- **Overall `bundle_multi_heldout.json` accuracy:** **63.3%** (19/30).

## Item 3 Proof: Generalized Taste & Named Format (Strict Job AND Format, n=40)
*Evaluated on `tests/taste_generalise.json` (n=40 unseen tasks where history contains zero overlap with expected skills). Counts as right ONLY if both `job` AND `output` format match.*
| Persona | Preferred Format | Cold Start (v3.19.0 Baseline) | With Learned Taste (v3.20.0, Words / Semantic) | Explicit Named Format Respected |
| :--- | :--- | :---: | :---: | :---: |
| **Visual Learner (Animation)** | `animation` | 40.0% | **80.0% / 100.0%** | **100.0%** |
| **Deep Reader (Text / Prose)** | `text` | 70.0% | **100.0% / 100.0%** | **100.0%** |
| **Hands-on Engineer (Code / Patterns)** | `code` | 100.0% | **100.0% / 100.0%** | **100.0%** |
| **Video & Demo Producer (Video / Screencasts)** | `video` | 100.0% | **100.0% / 100.0%** | **100.0%** |

## Detailed Accuracy Across All Task Suites
| Suite | Tasks (n) | Type | Keyword | v1 | Hive (Words) | Hive + Meaning | Hive + Rerank | Precision (Hive) | Junk Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `search_bench (91-task benchmark)` | 91 | Tuned | 83.5% | 86.8% | 85.7% | 92.3% | **91.2%** | 69.0% | 0.0% |
| `stack_eval (real projects)` | 24 | Tuned | 25.0% | 79.2% | 79.2% | 83.3% | **83.3%** | 49.6% | 0.0% |
| `search_reworded` | 35 | Tuned | 51.4% | 51.4% | 48.6% | 62.9% | **65.7%** | 34.5% | 0.0% |
| `precision_tuning` | 40 | Tuned | 35.0% | 52.5% | 100.0% | 100.0% | **100.0%** | 86.9% | 0.0% |
| `hive_heldout (3.19 held-out)` | 22 | 3.19 Held-Out | 9.1% | 63.6% | 90.9% | 90.9% | **90.9%** | 46.6% | 0.0% |
| `search_reworded_holdout (3.19 held-out)` | 35 | 3.19 Held-Out | 22.9% | 34.3% | 31.4% | 37.1% | **40.0%** | 22.4% | 0.0% |
| `plain_words_holdout2 (3.19 held-out)` | 40 | 3.19 Held-Out | 30.0% | 37.5% | 35.0% | 40.0% | **40.0%** | 23.3% | 0.0% |
| `final_heldout_plain (230cc07)` | 60 | Earlier Held-Out | 43.3% | 45.0% | 41.7% | 46.7% | **50.0%** | 26.0% | 0.0% |
| `final_heldout_project (230cc07)` | 30 | Earlier Held-Out | 40.0% | 66.7% | 63.3% | 63.3% | **63.3%** | 40.8% | 3.3% |
| `final_heldout_reworded (230cc07)` | 40 | Earlier Held-Out | 60.0% | 70.0% | 57.5% | 52.5% | **52.5%** | 27.5% | 0.0% |
| `precision_heldout (3.20 frozen)` | 40 | **Frozen Held-Out** | 22.5% | 22.5% | 87.5% | 87.5% | **87.5%** | 76.5% | 0.0% |
| `final_heldout_plain_v2 (02b0485)` | 60 | **Frozen v2 Held-Out** | 100.0% | 98.3% | 95.0% | 98.3% | **98.3%** | 81.2% | 0.0% |
| `final_heldout_project_v2 (02b0485)` | 30 | **Frozen v2 Held-Out** | 90.0% | 93.3% | 96.7% | 96.7% | **96.7%** | 77.8% | 0.0% |
| `final_heldout_reworded_v2 (02b0485)` | 40 | **Frozen v2 Held-Out** | 100.0% | 100.0% | 92.5% | 95.0% | **95.0%** | 85.4% | 0.0% |

## Stage-by-Stage Loss Analysis on Suites Below 80%
For the earlier held-out suites (`230cc07` and 3.19 held-out) that remain below 80% after adding the `clears_confidence` precision gate:
1. **`final_heldout_plain` (n=60, 50.0% hit / 30 missed):**
   - **Stage 1 (Candidate Recall — not in top-20 RRF pool):** 11 tasks (36.7% of misses) use colloquial phrasing with zero stem overlap and low embedding cosine (`< 0.42`) to the target skill's description.
   - **Stage 2 (Confidence Gate — rejected by `clears_confidence`):** 14 tasks (46.7% of misses) had the target skill in the candidate pool with 1 generic word hit (`num_hits == 1`) and `cos < 0.65`, which `clears_confidence` drops to keep the junk rate at 0.0% on negative/micro-edit tasks.
   - **Stage 3 (Ranked below top-3 stack limit):** 5 tasks (16.7% of misses).
2. **`final_heldout_reworded` (n=40, 52.5% hit / 19 missed):**
   - **Stage 1 (Candidate Recall):** 8 tasks (42.1% of misses).
   - **Stage 2 (Confidence Gate `clears_confidence`):** 8 tasks (42.1% of misses) dropped because the reworded prompt intentionally stripped all domain/technology terms, leaving 0 or 1 stem hits.
   - **Stage 3 (Ranked low):** 3 tasks (15.8% of misses).
3. **`precision_heldout` Mean Precision (76.5% with models, 79.8% words-only vs 80.0% target):**
   - **Hit rate is 87.5% and Junk Rate is 0.0%** (zero `avoid` skills and 14/15 negative tasks return `[]`). The 3.5-point gap on mean precision comes exclusively from 6 positive tasks where SFP attached a 2nd or 3rd supporting skill (e.g. `verification-loop` or `tdd-workflow`) alongside the right lead skill, and the narrow human `expect` list only named 1 skill (scoring that task 50% precision instead of 100%).

## Context Efficiency
- **Full Library Descriptions (carried by agents):** 81,691 tokens across 1,065 skills.
- **Full Library Body Text:** 1,907,869 tokens.
- **SFP Stack Load:** 3,985 tokens average context footprint.
- **Context Saved (vs Descriptions):** **95.1% reduction** (headline figure).
- **Context Saved (vs Full Body):** **99.8% reduction**.
