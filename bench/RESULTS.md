# Results for SFP 3.20.1

Written by `python3 bench/release.py` on 2026-11-26 at commit `03453dd`. The README and every image use the same data ([results/release.json](results/release.json)).

A task counts as right when the chosen skills include one a person marked correct for it. Each cell shows **right skill chosen / right skill first**.

## Every set

| Set | Tasks | Kind | Keyword search | SFP, no model | SFP + bge-m3 |
|---|---:|---|---:|---:|---:|
| `plain_words_holdout2` | 40 | regression | 35% / 30% | 40% / 28% | 55% / 40% |
| `search_reworded_holdout` | 35 | regression | 26% / 17% | 40% / 34% | 51% / 40% |
| `final_heldout_plain` | 60 | regression | 50% / 35% | 62% / 43% | 67% / 53% |
| `final_heldout_reworded` | 40 | regression | 62% / 50% | 75% / 58% | 78% / 58% |
| `hive_heldout` | 22 | regression | 18% / 9% | 91% / 68% | 86% / 64% |
| `final_heldout_project` | 30 | regression | 47% / 30% | 67% / 60% | 67% / 57% |
| `stack_eval` | 24 | tuned | 25% / 21% | 79% / 62% | 83% / 62% |
| `precision_heldout` | 15 | regression | 60% / 60% | 67% / 60% | 87% / 60% |
| `precision_heldout`, tasks that need no skill, left empty | 25 | regression | 0% | 92% | 84% |

**Regression** sets were never used to train or tune a weight, but their totals were looked at after each change, so a brand new set may score a little lower. **Tuned** sets were used.

## How often the right skill is on the map

| Best skills shown | SFP, no model | SFP + bge-m3 |
|---:|---:|---:|
| 3 | 57.7% | 64.6% |
| 10 | 71.4% | 81.7% |
| 24 | 81.1% | 86.9% |
| 40 | 84.0% | 93.1% |
| 60 | 86.9% | 95.4% |

On the 175 plain tasks. The agent is shown the best 40, grouped in towers, in about 1226 tokens.

## Taste, simulated learners

| Learner | Tasks | First pick in the liked format and the right job, before | after | Named formats followed |
|---|---:|---:|---:|---:|
| Visual Learner (Animation) | 10 | 40% | 60% | 3 of 3 |
| Deep Reader (Text / Prose) | 10 | 30% | 30% | 2 of 3 |
| Hands-on Engineer (Code / Patterns) | 10 | 90% | 90% | 2 of 3 |
| Video & Demo Producer (Video / Screencasts) | 10 | 100% | 100% | 3 of 3 |

## Time and tokens

| | Keyword search | SFP, no model | SFP + bge-m3 |
|---|---:|---:|---:|
| Typical choice | 0 ms | 7 ms | 413 ms |
| Slowest 5% | 0 ms | 20 ms | 510 ms |
| Tokens loaded, average | - | 5896 | 6117 |

One laptop, models already loaded. Tokens are estimated at 4 characters each.

## What was withdrawn

Earlier pages reported two sets that do not test what they seemed to. On the "v2" sets plain keyword search scores 98%, because their tasks repeat the words of the skill they expect. On the "exam" a local model rated the picks and keyword search gets 93% under the same rating. Neither is used any more.
