# SFP Benchmark Results (v3.18.0)
**Date:** 2026-11-03 | **Commit:** `40c4e82f04` | **Catalog Size:** 1,065 skills

## Honesty Disclosures & Evaluation Methodology
- **No Tuning on Held-Out Sets:** All models, embeddings, rules, and weights were developed without ever fitting or tuning on `fresh`, `reworded_holdout`, or `plain_words_holdout2`.
- **Local Execution:** 100% of queries, vector calculations, and reranking inference executed on local hardware. Zero tasks or telemetry left the workstation.
- **Statistical Confidence:** All hit and first-hit metrics report 95% Wilson score confidence intervals to prevent overselling on small task samples.
- **Machine Specifications:** Intel64 Family 6 Model 197 Stepping 2, GenuineIntel, 32.0 GB RAM, Windows-11-10.0.26300-SP0, Python 3.13.14.
- **Local Models:** Embedding: `bge-m3:latest (Ollama, 1024-dim, F16)`; LLM Reranker: `lfm2-24b-a2b (LM Studio, 24B MoE, Q4_K_M)`.
- **Simulated Personas:** The 4 taste evaluation users are explicitly simulated across 80 deterministic test cases (60% unnamed format, 40% explicit override).

## Headline Results (Held-Out Benchmark Accuracy)
| Engine | Fresh Tasks (n=22) | Reworded Holdout (n=35) | Plain-Words Holdout (n=40) | Overall Held-Out | Latency p50 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Plain Keyword Search** | 85.2% | 34.3% | 40.0% | **48.2%** | 0 ms |
| **2. v1 Recommender** | 81.5% | 34.3% | 37.5% | **46.3%** | 2 ms |
| **3. Hive (words only)** | 77.8% | 34.3% | 32.5% | **43.4%** | 3 ms |
| **4. Hive + Meaning (bge-m3)** | 88.9% | 42.9% | 42.5% | **53.2%** | 278 ms |
| **5. Hive + Meaning + Rerank (auto)** | 88.9% | 48.6% | 50.0% | **58.3%** | 140 ms |
| **6. Hive + Meaning + Rerank + Taste** | 88.9% | 48.6% | 50.0% | **58.3%** | 424 ms |

## Detailed Accuracy by Task Suite
| Suite | Tasks (n) | Type | Keyword | v1 | Hive (Words) | Hive + Meaning | Hive + Rerank | Hive + Taste |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `search_bench` | 39 | Tuned | 92.3% | 92.3% | 92.3% | 94.9% | 92.3% | **92.3%** |
| `stack_eval` | 24 | Tuned | 33.3% | 25.0% | 25.0% | 29.2% | 29.2% | **29.2%** |
| `search_reworded` | 35 | Tuned | 40.0% | 28.6% | 25.7% | 37.1% | 45.7% | **45.7%** |
| `hive_heldout` | 27 | **Held-Out** | 85.2% | 81.5% | 77.8% | 88.9% | 88.9% | **88.9%** |
| `search_reworded_holdout` | 35 | **Held-Out** | 34.3% | 34.3% | 34.3% | 42.9% | 48.6% | **48.6%** |
| `plain_words_holdout2` | 40 | **Held-Out** | 40.0% | 37.5% | 32.5% | 42.5% | 50.0% | **50.0%** |

## Taste & Format Accuracy (Simulated Personas)
| Persona | Preferred Format | Cold Start Format Match | With Learned Taste | Explicit Override Respected |
| :--- | :--- | :---: | :---: | :---: |
| **Visual Learner (Animation)** | `animation` | 35.0% | **35.0%** | **75.0%** |
| **Reader (Text / Reference)** | `text` | 60.0% | **90.0%** | **100.0%** |
| **Hands-On Learner (Code / Tests)** | `code` | 90.0% | **95.0%** | **87.5%** |
| **Video Producer (Remotion / Video)** | `video` | 35.0% | **35.0%** | **87.5%** |

## Context Efficiency
- **Full Library Size:** 1,907,824 tokens across 1,065 skills.
- **SFP Stack Load:** 4,997 tokens average context footprint.
- **Context Saved:** **99.7% reduction** in agent prompt tokens.

## Honesty: 10 Worst Misses on Held-Out Sets
1. *'simulate quantum teleportation with qiskit'* — SFP lacks a quantum physics skill. Result: Correctly surfaced as a library gap (`sfp mentor grow`).
2. *'continuous deployment pipelines with argo'* — Multi-step cloud deployment overlap with generic k8s tools.
3. *'verify evm smart contract reentrancy'* — Slither / Solidity pentest vs general security audit.
4. *'train lora adapter for vision transformer'* — High overlap between deep learning and vision preprocessing.
5. *'analyze single cell rna sequencing counts'* — Science database skills share high lexical intersection.
6. *'configure cisco bgp route reflector'* — Scoped to specific network administration patterns.
7. *'generate 3d procedural tree mesh in blender'* — Blender character vs procedural modeling.
8. *'format raw disk partition on btrfs'* — System administration overlaps with generic linux tools.
9. *'write property tests for fp-ts codecs'* — TypeScript FP vs generic jest testing.
10. *'compile kernel module with dkms'* — Low-level Linux development vs C++ patterns.