# SFP Benchmark Results (v3.19.0)
**Date:** 2026-11-04 | **Commit:** `4a188a462b` | **Catalog Size:** 1,065 skills

## Honesty Disclosures & Evaluation Methodology
- **Scoring Parity:** `bench/run_all.py` uses `sfp_hive.load_cases()` and scores identically to `sfp_hive.evaluate()`. Keyword search uses `k = max(1, round(hive stack size))` as in `evaluate()`.
- **No Tuning on Held-Out Sets:** All models, embeddings, rules, and weights were developed without ever fitting or tuning on `fresh`, `reworded_holdout`, or `plain_words_holdout2`.
- **Engine 6 Taste Semantics:** On held-out sets where no user history exists, Engine 6 runs with an empty taste profile and equals Engine 5. In the Persona Taste Evaluation, Engine 6 runs with seeded history per persona in an isolated temporary `SFP_DATA_DIR`.
- **Skill Cards Verification:** 60 randomly sampled skill cards are stored in `bench/cards_check.json` with `checked: null` for human auditing. Automated heuristic vs model agreement across all 1,065 skills is **83.6%**.
- **Context Token Savings:** Both full body text (1,907,824 tokens) and description metadata (81,931 tokens) are reported. The headline uses the smaller, conservative figure (**94%** reduction vs loading all descriptions).
- **Data Isolation:** All benchmark runs strictly set `SFP_DATA_DIR` to an isolated temporary directory; real user data in `~/.sfp` is guaranteed untouched.
- **Machine Specifications:** Intel64 Family 6 Model 197 Stepping 2, GenuineIntel, 32.0 GB RAM, Windows-11-10.0.26300-SP0, Python 3.13.14.
- **Local Models:** Embedding: `bge-m3:latest (Ollama, 1024-dim, F16)`; LLM Reranker: `lfm2-24b-a2b (LM Studio, 24B MoE, Q4_K_M)` (never routed to port 8787 or cloud).

## Headline Results (Held-Out Benchmark Accuracy)
| Engine | Fresh Tasks (n=22) | Reworded Holdout (n=35) | Plain-Words Holdout (n=40) | Overall Held-Out | Latency p50 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Plain Keyword Search** | 9.1% | 25.7% | 32.5% | **24.7%** | 0 ms |
| **2. v1 Recommender** | 63.6% | 34.3% | 37.5% | **42.3%** | 1 ms |
| **3. Hive (words only)** | 90.9% | 34.3% | 35.0% | **47.4%** | 2 ms |
| **4. Hive + Meaning (bge-m3)** | 90.9% | 40.0% | 52.5% | **56.7%** | 186 ms |
| **5. Hive + Meaning + Rerank (auto)** | 90.9% | 51.4% | 55.0% | **61.9%** | 116 ms |
| **6. Hive + Meaning + Rerank + Taste** | 90.9% | 51.4% | 55.0% | **61.9%** | 116 ms |

## Detailed Accuracy by Task Suite
| Suite | Tasks (n) | Type | Keyword | v1 | Hive (Words) | Hive + Meaning | Hive + Rerank | Hive + Taste |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `search_bench (eval+holdout+fresh)` | 91 | Tuned | 83.5% | 86.8% | 86.8% | 93.4% | 93.4% | **93.4%** |
| `stack_eval (with real projects)` | 24 | Tuned | 25.0% | 79.2% | 79.2% | 79.2% | 79.2% | **79.2%** |
| `search_reworded` | 35 | Tuned | 34.3% | 28.6% | 28.6% | 40.0% | 54.3% | **54.3%** |
| `hive_heldout` | 22 | **Held-Out** | 9.1% | 63.6% | 90.9% | 90.9% | 90.9% | **90.9%** |
| `search_reworded_holdout` | 35 | **Held-Out** | 25.7% | 34.3% | 34.3% | 40.0% | 51.4% | **51.4%** |
| `plain_words_holdout2` | 40 | **Held-Out** | 32.5% | 37.5% | 35.0% | 52.5% | 55.0% | **55.0%** |

## Taste & Format Accuracy (Held-Out Tasks, n=40)
Tasks evaluated on 40 completely new held-out topics chosen by card (job + output), with no hard-coded skill names.
| Persona | Preferred Format | Cold Start Format Match | With Learned Taste | Explicit Override Respected |
| :--- | :--- | :---: | :---: | :---: |
| **Visual Learner (Animation)** | `animation` | 20.0% | **90.0%** | **66.7%** |
| **Deep Reader (Text / Prose)** | `text` | 40.0% | **100.0%** | **100.0%** |
| **Hands-on Engineer (Code / Patterns)** | `code` | 80.0% | **90.0%** | **66.7%** |
| **Video & Demo Producer (Video / Screencasts)** | `video` | 90.0% | **90.0%** | **66.7%** |

### Taste & Format Accuracy (Tuning Set, n=80)
| Persona | Preferred Format | Cold Start Format Match | With Learned Taste | Explicit Override Respected |
| :--- | :--- | :---: | :---: | :---: |
| **Visual Learner (Animation)** | `animation` | 35.0% | **90.0%** | **75.0%** |
| **Reader (Text / Reference)** | `text` | 65.0% | **100.0%** | **100.0%** |
| **Hands-On Learner (Code / Tests)** | `code` | 90.0% | **95.0%** | **87.5%** |
| **Video Producer (Remotion / Video)** | `video` | 50.0% | **95.0%** | **100.0%** |

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
- **Full Library Descriptions (carried by agents):** 81,931 tokens across 1,065 skills.
- **Full Library Body Text:** 1,907,824 tokens.
- **SFP Stack Load:** 4,513 tokens average context footprint.
- **Context Saved (vs Descriptions):** **94.5% reduction** (headline figure).
- **Context Saved (vs Full Body):** **99.8% reduction**.

## Honesty: Tasks Where Plain Search Hit and Hive Words-Only Missed
On `plain_words_holdout2.json` (40 held-out tasks phrased in conversational beginner language), Hive Words-Only achieved 35.0% vs Plain Search 32.5%. The two tasks where Plain Search found the expected skill in its top-k but Hive's words signal did not engage were:
1. *'turn my spreadsheet rows into a database table'* (Expected: `database-migrations`, `postgres-patterns`, `clickhouse-io`).
   - *Reason:* Plain search matched `database` literally to `database-migrations`. The Hive's vocabulary layer suppressed raw keyword hits because the term `spreadsheet` suggested data engineering while `database-migrations` was categorized under schema lifecycle. When meaning (`bge-m3`) is active, the Hive recovers this task.
2. *'make a diagram of my microservices architecture'* (Expected: `diagram-design`, `architecture-decision-records`).
   - *Reason:* Plain search retrieved `diagram-design` at rank 1. In words-only mode without UI context, the Hive selected `design-systems` due to high token overlap with `microservices architecture`. When meaning is enabled, `diagram-design` is promoted.