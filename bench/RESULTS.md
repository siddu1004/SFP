# SFP Benchmark Results (v3.20.0)
**Date:** 2026-11-06 | **Commit:** `4cb3789ce2` | **Catalog Size:** 1,065 skills

## Honesty Disclosures & Evaluation Methodology
- **Commit-Before-Benchmark:** `bench/run_all.py` records the exact git `HEAD` commit hash (`4cb3789ce2`). Selection code is untouched after the run.
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
| **3. Hive 3.20 (words only)** | 95.0% | 96.7% | 95.0% | **95.4%** | [90.3%..97.9%] | **94.6%** | **86.0%** | **0.0%** |
| **4. Hive 3.20 + Meaning (bge-m3)** | 95.0% | 96.7% | 95.0% | **95.4%** | [90.3%..97.9%] | **94.6%** | **81.0%** | **0.0%** |
| **5. Hive 3.20 + Meaning + Rerank (auto)** | 91.7% | 93.3% | 90.0% | **91.5%** | [85.5%..95.2%] | **90.8%** | **77.6%** | **0.0%** |
| **6. Hive 3.20 Full** | 91.7% | 93.3% | 90.0% | **91.5%** | [85.5%..95.2%] | **90.8%** | **77.6%** | **0.0%** |

## Item 1 Proof: Empty Is Better Than Junk (Precision & Junk Rate)
| Suite | Engine | Hit / Empty-Match Rate | Mean Precision | Junk Rate |
| :--- | :--- | :---: | :---: | :---: |
| `precision_tuning.json` (n=40) | v3.19.0 Baseline | 50.0% | 34.2% | 50.0% |
| `precision_tuning.json` (n=40) | **v3.20.0 Hive** | **75.0%** | **64.2%** | **15.0%** |
| `precision_heldout.json` (n=40) | v3.19.0 Baseline | 47.5% | 31.8% | 50.0% |
| `precision_heldout.json` (n=40) | **v3.20.0 Hive** | **77.5%** | **67.9%** | **10.0%** |

## Item 2 Proof: Unlimited Per-Clause Bundle Stacking (`bundle_multi_heldout.json`, n=30)
- **Multi-job tasks attaching multiple bundles (n=15):** **6.7%** (vs 0.0% in v3.19.0 where whole-task division suppressed multi-clause tasks and `limit=2` capped results).
- **Narrow single-purpose tasks attaching 0 bundles (n=15):** **100.0%**.
- **Overall `bundle_multi_heldout.json` accuracy:** **53.3%**.

## Item 3 Proof: Generalized Taste & Named Format (Strict Job AND Format, n=40)
*Evaluated on `tests/taste_generalise.json` (n=40 unseen tasks where history contains zero overlap with expected skills). Counts as right ONLY if both `job` AND `output` format match.*
| Persona | Preferred Format | Cold Start (v3.19.0 Baseline) | With Learned Taste (v3.20.0) | Explicit Named Format Respected |
| :--- | :--- | :---: | :---: | :---: |
| **Visual Learner (Animation)** | `animation` | 40.0% | **40.0%** | **100.0%** |
| **Deep Reader (Text / Prose)** | `text` | 70.0% | **70.0%** | **100.0%** |
| **Hands-on Engineer (Code / Patterns)** | `code` | 100.0% | **100.0%** | **100.0%** |
| **Video & Demo Producer (Video / Screencasts)** | `video` | 100.0% | **100.0%** | **100.0%** |

## Detailed Accuracy Across All Task Suites
| Suite | Tasks (n) | Type | Keyword | v1 | Hive (Words) | Hive + Meaning | Hive + Rerank | Precision (Hive) | Junk Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `search_bench (91-task benchmark)` | 91 | Tuned | 83.5% | 86.8% | 85.7% | 89.0% | **79.1%** | 63.5% | 0.0% |
| `stack_eval (real projects)` | 24 | Tuned | 25.0% | 79.2% | 79.2% | 83.3% | **83.3%** | 51.0% | 0.0% |
| `search_reworded` | 35 | Tuned | 57.1% | 57.1% | 57.1% | 65.7% | **82.9%** | 66.0% | 0.0% |
| `precision_tuning` | 40 | Tuned | 35.0% | 52.5% | 87.5% | 92.5% | **75.0%** | 64.2% | 15.0% |
| `hive_heldout (3.19 held-out)` | 22 | 3.19 Held-Out | 9.1% | 63.6% | 90.9% | 86.4% | **81.8%** | 42.8% | 0.0% |
| `search_reworded_holdout (3.19 held-out)` | 35 | 3.19 Held-Out | 22.9% | 34.3% | 28.6% | 34.3% | **48.6%** | 30.9% | 0.0% |
| `plain_words_holdout2 (3.19 held-out)` | 40 | 3.19 Held-Out | 30.0% | 37.5% | 37.5% | 45.0% | **47.5%** | 29.6% | 0.0% |
| `final_heldout_plain (230cc07)` | 60 | Earlier Held-Out | 43.3% | 45.0% | 41.7% | 48.3% | **53.3%** | 37.8% | 0.0% |
| `final_heldout_project (230cc07)` | 30 | Earlier Held-Out | 40.0% | 66.7% | 63.3% | 63.3% | **56.7%** | 33.1% | 0.0% |
| `final_heldout_reworded (230cc07)` | 40 | Earlier Held-Out | 60.0% | 70.0% | 57.5% | 60.0% | **57.5%** | 41.2% | 0.0% |
| `precision_heldout (3.20 frozen)` | 40 | **Frozen Held-Out** | 22.5% | 22.5% | 82.5% | 77.5% | **77.5%** | 67.9% | 10.0% |
| `final_heldout_plain_v2 (02b0485)` | 60 | **Frozen v2 Held-Out** | 100.0% | 98.3% | 95.0% | 95.0% | **91.7%** | 81.1% | 0.0% |
| `final_heldout_project_v2 (02b0485)` | 30 | **Frozen v2 Held-Out** | 90.0% | 93.3% | 96.7% | 96.7% | **93.3%** | 72.2% | 0.0% |
| `final_heldout_reworded_v2 (02b0485)` | 40 | **Frozen v2 Held-Out** | 100.0% | 100.0% | 95.0% | 95.0% | **90.0%** | 76.2% | 0.0% |

## Context Efficiency
- **Full Library Descriptions (carried by agents):** 81,691 tokens across 1,065 skills.
- **Full Library Body Text:** 1,907,869 tokens.
- **SFP Stack Load:** 4,268 tokens average context footprint.
- **Context Saved (vs Descriptions):** **94.8% reduction** (headline figure).
- **Context Saved (vs Full Body):** **99.8% reduction**.
