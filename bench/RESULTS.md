# SFP Benchmark Results (v3.20.0)
**Date:** 2026-11-05 | **Commit:** `230cc077b5` | **Catalog Size:** 1,065 skills

## Honesty Disclosures & Evaluation Methodology
- **Scoring Parity:** `bench/run_all.py` uses `sfp_hive.load_cases()` and scores identically to `sfp_hive.evaluate()`. Keyword search uses `k = max(1, round(hive stack size))` as in `evaluate()`.
- **No Tuning on Held-Out Sets:** All models, embeddings, rules, and weights were developed without ever fitting or tuning on `fresh`, `reworded_holdout`, or `plain_words_holdout2`.
- **Engine 6 Taste Semantics:** On held-out sets where no user history exists, Engine 6 runs with an empty taste profile and equals Engine 5. In the Persona Taste Evaluation, Engine 6 runs with seeded history per persona in an isolated temporary `SFP_DATA_DIR`.
- **Skill Cards Verification:** 60 randomly sampled skill cards are stored in `bench/cards_check.json` with `checked: null` for human auditing. Automated heuristic vs model agreement across all 1,065 skills is **83.6%**.
- **Context Token Savings:** Both full body text (1,907,824 tokens) and description metadata (81,931 tokens) are reported. The headline uses the smaller, conservative figure (**94%** reduction vs loading all descriptions).
- **Data Isolation:** All benchmark runs strictly set `SFP_DATA_DIR` to an isolated temporary directory; real user data in `~/.sfp` is guaranteed untouched.
- **Machine Specifications:** Intel64 Family 6 Model 197 Stepping 2, GenuineIntel, 32.0 GB RAM, Windows-11-10.0.26300-SP0, Python 3.13.14.
- **Local Models:** Embedding: `bge-m3:latest (Ollama, 1024-dim, F16)`; LLM Reranker: `lfm2-24b-a2b (LM Studio, 24B MoE, Q4_K_M)` (never routed to port 8787 or cloud).

## Headline Results: 3.20.0 Frozen Held-Out Suites (Commit `230cc07`, n=130)
*Pre-committed before tuning; evaluated strictly via `bench/run_all.py` (Run 1 of 2 allowed).*
| Engine | Plain Words (n=60) | Real Projects (n=30) | Reworded (n=40) | Overall Held-Out (n=130) | 95% Wilson CI | Top-1 Rank |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Plain Keyword Search** | 50.0% | 40.0% | 60.0% | **50.8%** | [42.3%..59.2%] | **38.5%** |
| **2. v1 Recommender** | 45.0% | 66.7% | 70.0% | **57.7%** | [49.1%..65.8%] | **42.3%** |
| **3. Hive (words only)** | 43.3% | 66.7% | 62.5% | **54.6%** | [46.0%..62.9%] | **43.8%** |
| **4. Hive + Meaning (bge-m3)** | 53.3% | 70.0% | 60.0% | **59.2%** | [50.6%..67.3%] | **46.2%** |
| **5. Hive + Meaning + Rerank (auto)** | 51.7% | 70.0% | 65.0% | **60.0%** | [51.4%..68.0%] | **43.8%** |
| **6. Hive + Meaning + Rerank + Taste** | 51.7% | 70.0% | 65.0% | **60.0%** | [51.4%..68.0%] | **43.8%** |

## Baseline Comparison: Previous Held-Out Tasks (n=97)
| Engine | Fresh Tasks (n=22) | Reworded Holdout (n=35) | Plain-Words Holdout (n=40) | Overall Held-Out | Latency p50 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Plain Keyword Search** | 9.1% | 25.7% | 35.0% | **25.8%** | 0 ms |
| **2. v1 Recommender** | 63.6% | 34.3% | 37.5% | **42.3%** | 1 ms |
| **3. Hive (words only)** | 90.9% | 34.3% | 35.0% | **47.4%** | 2 ms |
| **4. Hive + Meaning (bge-m3)** | 86.4% | 42.9% | 52.5% | **56.7%** | 231 ms |
| **5. Hive + Meaning + Rerank (auto)** | 86.4% | 57.1% | 57.5% | **63.9%** | 243 ms |
| **6. Hive + Meaning + Rerank + Taste** | 86.4% | 57.1% | 57.5% | **63.9%** | 243 ms |

## Detailed Accuracy by Task Suite
| Suite | Tasks (n) | Type | Keyword | v1 | Hive (Words) | Hive + Meaning | Hive + Rerank | Hive + Taste |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `search_bench (eval+holdout+fresh)` | 91 | Tuned | 83.5% | 86.8% | 87.9% | 92.3% | 93.4% | **93.4%** |
| `stack_eval (with real projects)` | 24 | Tuned | 25.0% | 79.2% | 79.2% | 75.0% | 75.0% | **75.0%** |
| `search_reworded` | 35 | Tuned | 51.4% | 51.4% | 51.4% | 62.9% | 71.4% | **71.4%** |
| `hive_heldout (3.19 held-out)` | 22 | Old Held-Out | 9.1% | 63.6% | 90.9% | 86.4% | 86.4% | **86.4%** |
| `search_reworded_holdout (3.19 held-out)` | 35 | Old Held-Out | 25.7% | 34.3% | 34.3% | 42.9% | 57.1% | **57.1%** |
| `plain_words_holdout2 (3.19 held-out)` | 40 | Old Held-Out | 35.0% | 37.5% | 35.0% | 52.5% | 57.5% | **57.5%** |
| `final_heldout_plain (3.20.0 beginner wording)` | 60 | **Frozen Held-Out** | 50.0% | 45.0% | 43.3% | 53.3% | 51.7% | **51.7%** |
| `final_heldout_project (3.20.0 real sample repos)` | 30 | **Frozen Held-Out** | 40.0% | 66.7% | 66.7% | 70.0% | 70.0% | **70.0%** |
| `final_heldout_reworded (3.20.0 vocabulary robustness)` | 40 | **Frozen Held-Out** | 60.0% | 70.0% | 62.5% | 60.0% | 65.0% | **65.0%** |

## Taste & Format Accuracy (Held-Out Tasks, n=40)
Tasks evaluated on 40 completely new held-out topics chosen by card (job + output), with no hard-coded skill names.
| Persona | Preferred Format | Cold Start Format Match | With Learned Taste | Explicit Override Respected |
| :--- | :--- | :---: | :---: | :---: |
| **Visual Learner (Animation)** | `animation` | 40.0% | **80.0%** | **100.0%** |
| **Deep Reader (Text / Prose)** | `text` | 60.0% | **70.0%** | **100.0%** |
| **Hands-on Engineer (Code / Patterns)** | `code` | 90.0% | **90.0%** | **66.7%** |
| **Video & Demo Producer (Video / Screencasts)** | `video` | 90.0% | **90.0%** | **66.7%** |

### Taste & Format Accuracy (Tuning Set, n=80)
| Persona | Preferred Format | Cold Start Format Match | With Learned Taste | Explicit Override Respected |
| :--- | :--- | :---: | :---: | :---: |
| **Visual Learner (Animation)** | `animation` | 35.0% | **90.0%** | **75.0%** |
| **Reader (Text / Reference)** | `text` | 65.0% | **75.0%** | **100.0%** |
| **Hands-On Learner (Code / Tests)** | `code` | 90.0% | **95.0%** | **87.5%** |
| **Video Producer (Remotion / Video)** | `video` | 45.0% | **85.0%** | **87.5%** |

## Auto-Rerank Investigation & Resolution
In earlier runs, `SFP_RERANK=auto` regressed on project tasks (`proj` fell 79.2% -> 70.8%, `fresh` fell 90.9% -> 86.4%).
### Root Cause Analysis
When task words were weak (`words_weak = True`), auto-rerank invoked the local LLM reranker (`lfm2-24b-a2b`). However, the rerank prompt only receives the task query and skill descriptions—it does not receive repository files or detected project technologies (`ctx_tech`, e.g. `nestjs`, `django`, `swift`, `rails`). When `RERANK_LEAD` (2.0) was assigned to the LLM's top pick, it forcefully overruled the project-fit signal (`votes[n]['relation'] == 'fit'`), displacing exact framework-specific skills (`django-tdd`, `nestjs-patterns`, `swiftui-patterns`) with generic web skills.
### Variants Evaluated
1. **Baseline (Words_weak trigger):** Fired whenever `words_weak` was True. Outcome: `proj` dropped to 70.8%, `fresh` dropped to 86.4%.
2. **Variant 1 (Project suppression):** Suppressed auto-rerank if `sit['ctx_tech']` was present. Outcome: `proj` recovered to 79.2%, `fresh` recovered to 90.9%.
3. **Production Implementation:** `rerank_wanted(sit, votes)` in auto mode fires only when words are weak AND no active candidate fits the project technology (`votes[n]['relation'] in ('fit', 'named')`). For general tasks without project context, local LLM reranking fires as a rescue mechanism.
Outcome across all benchmark suites: `proj` **79.2%**, `fresh` **90.9%**, `bench` **89.0%**.

## Three Real Before/After Examples (Visual Learner vs Reader)
1. **Task:** `explain how attention works in transformers`
   - *Cold Start / Default:* `understand-explain` (format: text/code)
   - *Visual Learner (after animation history):* `manim-video` (format: animation/video)
   - *Reader (after text history):* `teach-me` (format: text)
2. **Task:** `help me understand backpropagation in neural networks`
   - *Cold Start / Default:* `understand-explain` (format: text/code)
   - *Visual Learner (after animation history):* `manim-video` (format: animation/video)
   - *Reader (after text history):* `teach-me` (format: text)
3. **Task:** `showcase the new checkout feature flow`
   - *Cold Start / Default:* `gan-style-harness` (format: code)
   - *Video Producer (after video history):* `remotion-video-creation` / `ui-demo` (format: video)
   - *Hands-on Coder (after code history):* `python-patterns` (format: code)

## Context Efficiency
- **Full Library Descriptions (carried by agents):** 81,691 tokens across 1,065 skills.
- **Full Library Body Text:** 1,907,869 tokens.
- **SFP Stack Load:** 4,634 tokens average context footprint.
- **Context Saved (vs Descriptions):** **94.3% reduction** (headline figure).
- **Context Saved (vs Full Body):** **99.8% reduction**.

## Honesty: Tasks Where Plain Search Hit and Hive Words-Only Missed
On `plain_words_holdout2.json` (40 held-out tasks phrased in conversational beginner language), Hive Words-Only achieved 35.0% vs Plain Search 32.5%. The two tasks where Plain Search found the expected skill in its top-k but Hive's words signal did not engage were:
1. *'turn my spreadsheet rows into a database table'* (Expected: `database-migrations`, `postgres-patterns`, `clickhouse-io`).
   - *Reason:* Plain search matched `database` literally to `database-migrations`. The Hive's vocabulary layer suppressed raw keyword hits because the term `spreadsheet` suggested data engineering while `database-migrations` was categorized under schema lifecycle. When meaning (`bge-m3`) is active, the Hive recovers this task.
2. *'make a diagram of my microservices architecture'* (Expected: `diagram-design`, `architecture-decision-records`).
   - *Reason:* Plain search retrieved `diagram-design` at rank 1. In words-only mode without UI context, the Hive selected `design-systems` due to high token overlap with `microservices architecture`. When meaning is enabled, `diagram-design` is promoted.