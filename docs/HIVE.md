# The Hive

`sfp-hive` chooses which skills an agent loads for a task, and in what order, and it learns from feedback. Its code is `mcp/sfp_hive.py` (the selection) and `mcp/sfp_learn.py` (the feedback loop and the learned model). The model is a honeybee colony: signals are scouts, agreement is quorum, overlap suppression is stop signals, roles follow response thresholds, history is a fading trail, and feedback reinforces or abandons a skill for the words of a task. The README has the full mapping. This page covers the algorithm, the learning, how both were measured and built (including what failed), where they fail, and what to build next.

## What problem it solves

An agent reads the name and description of every installed skill at the start of every session, so installing hundreds is expensive, and installing a few misses the good ones. Keyword search finds skills that share words with the task but ignores the project: "write tests" is a different skill in a Django app and a Rust crate. The hive decides which few skills this task needs in this project, and corrects itself when you tell it it was wrong.

## Selection

For each task it combines five independent signals, requires them to agree, removes overlap and gives every chosen skill a job.

```text
select(task, project, goal, skills used so far, learned model):
  1. read the situation
       words    the task's words, minus filler ("add", "write"), synonyms joined
       project  technologies from manifests and file types (scan cached 30 s)
       demand   share of each job (plan, build, test ...) the task and goal ask for
  2. collect signals, for every skill the words, the model or the history can reach
       words     search relevance, normalised to the best match
       project   fit with the project's technology; no opinion for a general skill;
                 0 for another technology ("mismatch") or one nobody named
       role      cosine between the task's demand and the skill's jobs
       category  how much the task's words point at the skill's category
       history   how often this skill follows the one used just before
  3. agreement: keep a skill only if its words are strong (0.8 or more), or two signals back it
     (0.3 or more each), and it is not for another technology than the project's
  4. quality = words x (1 + 0.3 category) x (0.85 + 0.3 role) x (1 + 0.5 project) x (1 + 0.3 history)
               x exp(learned preference), normalised so the best is 1
  5. assemble, until four skills or nothing is left:
       left  = quality - 0.5 x the largest overlap with any chosen skill
       take the skill with the most left; stop if nothing is left
       its response to each job = s^2 / (s^2 + theta^2), with s = need x left
       if the best response is under 0.2 (and something is already chosen), it stays in reserve
       if it would break the token budget (12,000 by default), it stays in reserve
       otherwise it takes that job, and the job's need drops by 0.6 x the response
  6. order by phase of work; label base, check, finish; say which signals backed each skill
  7. suggest what usually follows the last skill
```

Overlap between two skills is their similarity (names count as much as descriptions), plus 0.5 if they do the same job in the same category. So two near-identical MCP builders suppress each other, while unit testing and end-to-end testing, which share a job but do different parts of it, can both stay.

### Where the ideas come from

The structure follows models of collective decision making and division of labour in social insects, used here as engineering ideas:

| Mechanism | Source | Used for |
|---|---|---|
| Independent assessors must reach agreement before a choice is made | Honeybee nest-site selection (Seeley, *Honeybee Democracy*, 2010) | Agreement: one noisy signal cannot decide |
| Rival options suppress each other (cross-inhibition) | Seeley et al., *Science*, 2012 | Overlap suppression |
| An individual takes a job when its need passes a threshold, and doing it lowers the need: probability s^2 / (s^2 + theta^2) | Bonabeau, Theraulaz and Deneubourg, 1996 | Role allocation: a job gets one or two skills, an unneeded job none |
| Reinforcement that evaporates | Ant colony optimisation (Dorigo, 1992) | History: recorded sequences with a 30-day half-life |

A queen bee does not assign work in a colony; the division of labour emerges from local rules like these, which is why they suit a decision with no central authority that must still be consistent.

### The history signal

A first-order Markov chain over skills, smoothed by category and job:

```text
P(b | a) = lam x c(a, b) / c(a)  +  (1 - lam) x back-off(b | a)
lam      = c(a) / (c(a) + number of distinct skills seen after a)      (Witten-Bell)
back-off = 0.5 x P(category of b | category of a) / size of that category
         + 0.5 x P(phase of b | phase of a) / number of skills in that phase
```

Counts come from the 18 recipes in `mcp/stack_recipes.json` (each step counts twice) and from the stacks of decisions you reported as helpful, weighted by 2^(-age / 30 days). Every row sums to 1; a test checks it.

## Learning from feedback

The hive makes a decision. The learner closes the loop, in four steps.

1. **Log the decision.** Every `select` records the skills chosen, the project's main technologies, the stems of the task's main words, and the strongest candidates' signal votes, in `~/.sfp/decisions.jsonl`, with an id.
2. **Collect feedback.** After the task, the agent or the user reports, by decision id (or `last`), which chosen skills `helped`, were `unhelpful`, were `ignored` (chosen but never used) and which were `missing` (should have been chosen). `give_feedback` in MCP, `sfp_hive.py feedback` on the command line.
3. **Fit the model.** A regularised logistic regression whose features are (task word, skill) pairs, valued higher for rarer words, predicts whether a skill helps for a task with those words.
4. **Apply it.** The model's output z for a skill, bounded to +-1.2, scales the skill's quality by exp(z). A strong positive association also brings in a skill that the keyword search did not find, and can admit a skill that lacks agreement (z of 0.7 or more).

```text
minimise   sum_i  w_i x logloss(p_i, y_i)  +  0.5 x lambda x sum_f weight_f^2
p_i      = sigmoid( sum over the task's words  weight[word|skill] x rarity(word) )      (no bias term)
y_i      = 1 for helped and missing, 0 for unhelpful and ignored
w_i      = verdict weight (1.0; ignored 0.3) x 2^(-age / 120 days)
lambda   = 1.0, solved by damped diagonal Newton steps
```

Properties, each pinned by a test:

- **No feedback means no change.** Every weight is zero, so z is zero and the selection is identical to the unlearned one.
- **One report is damped.** A single helped or unhelpful report moves a skill's preference by roughly 0.3 to 0.7 for the words of that task, so no single report can remove the only good skill.
- **Mistakes teach the most.** The gradient is proportional to the error, so a skill reported unhelpful, or missing after being passed over, moves the model more than a confirmation of what it already believed.
- **It is task-conditional.** What is learned belongs to the words of a task. A skill demoted for "write tests for the order view" is still chosen for "set up background jobs with celery".
- **It is bounded and it fades.** Preferences are clamped, feedback loses weight with a 120-day half-life and is dropped after a year.
- **It is private by construction.** Only word stems of the task are stored, never sentences, file contents or paths. `SFP_LEARN_WORDS=0` stops recording words, `SFP_NO_LEARNING=1` stops all recording and learning, and `forget` deletes everything.

### How the learning was built, including what failed

The first design looked sensible and was wrong, and the measurement caught it.

1. **First design: global weights.** A weight per skill, per (skill, technology) and per signal (how much to trust the words, the project and so on), fitted by the same logistic regression. On 5-fold cross-validation over 137 tasks, repeated five times, it made unseen tasks worse: 86.8% fell to 84.8%, worse in 14 of 25 folds and better in 6. It fixed only 25% of the mistakes it was shown when the same task was asked again.
2. **An ablation showed why.** Dropping the weak "ignored" negatives, or the signal weights, or the aliases did not rescue it. Global per-skill and per-signal weights simply do not generalise: whether a skill helps depends on the task. A skill that helped on three tasks was wrongly favoured on a fourth. The "ignored" label was also noisy, because the answer key lists only some acceptable skills.
3. **Second design: task-conditional word features.** Features became (word, skill) pairs only, with the strength scaled by how rare the word is. A learned association also brings in a skill search missed, which replaced a separate alias list. In the same cross-validation: 94% of shown mistakes fixed on retry, unseen tasks 86.8% to 87.7%, better in 11 folds and worse in 5, and 8 of 685 evaluated tasks that were right became wrong. Adding global skill or signal weights back on top made it worse again, so they stayed out. The settings were chosen from a small sweep (regularisation 0.5 to 2, weights for "ignored" 0 to 0.3) and then fixed.

### Measured

`python3 mcp/sfp_hive.py learning-curve` reproduces this; `tests/test_learn.py` fails if it regresses. A simulated user reports feedback from the answer key on the training tasks of each fold: skills in the key helped, skills marked to avoid were unhelpful, other chosen skills were ignored, and an expected skill the hive missed is reported missing. The model is fitted once and scored on the held-out tasks.

| Measure | Result |
|---|---:|
| Mistakes on training tasks fixed when the same task is asked again | 94% |
| Unseen tasks answered correctly, without learning | 86.8% |
| Unseen tasks answered correctly, with learning | 87.7% |
| Folds improved, equal, worse (25 folds) | 11, 9, 5 |
| Right tasks that became wrong (of 685 evaluated) | 8 |
| Stacks with a skill for the wrong technology | 0 |

How far to trust it: the effect on unseen tasks is +0.9 points with a standard deviation of 3.4 points across folds, so it is within noise even though it leans the right way. The dependable result is the first row: a reported mistake is fixed. The feedback is simulated from an answer key, which is cleaner than real feedback (people forget to report, and misjudge). The benchmark has few repeated task types, which limits what any learner can show; a real user's repeated work is where it should do better, and that is not yet measured.

## Selection quality

`python3 mcp/sfp_hive.py evaluate` reproduces these, and the README's copy is regenerated on every sync. "Right" means the selection holds a skill that a person marked as correct for the task. Plain search gets about as many results as the hive's average selection.

| Task set | Hive | Earlier engine (v1) | Plain search |
|---|---:|---:|---:|
| 22 held-out tasks in 8 new projects (written first, scored once) | 86% | 68% | 14% |
| 24 tasks in 10 sample projects | 79% | 79% | 33% |
| 91 tasks with no project | 89% | 89% | 86% |
| Stacks with a skill for the wrong technology, all sets | 0 | 0 | 2 |

The hive's constants were tuned on the 24-task and 91-task sets, so those rows are optimistic. The held-out set was written before the final design and opened once. The tasks and the answers were written by one person. Nothing here measures whether the finished work is better.

## Speed

A decision takes a few milliseconds inside the process that asks. Medians on one machine (a shared cloud sandbox, so read the ratios):

| Step | 2.0.0 | Now | What changed |
|---|---:|---:|---|
| Search the library | 0.4 to 0.6 ms | 0.08 ms | A word-to-skills lookup, so a query scores only skills that share a word with it |
| Predict the next skill | 5 to 8 ms | 0.3 to 0.4 ms | Skills in the same category and job share one back-off value |
| One decision, project already scanned | 7.5 ms | 2 to 3 ms | The two changes above |
| Through the running MCP server, later calls | 15 to 27 ms | 3 to 5 ms | The same |
| MCP server, first call after start-up | 47 to 55 ms | 5 to 9 ms | The hive is loaded in the background while the client starts |
| One-shot command line call on this repo | 167 to 180 ms | 125 to 129 ms | A saved search index, a faster start-up |
| Scan a project of 1,495 files | 28 to 40 ms | 27 to 41 ms | Unchanged: it is mostly the cost of walking folders |

Every speed change was checked against a recorded copy of the output on all 137 evaluation tasks, byte for byte, and `tests/test_speed.py` keeps each fast path equal to the plain definition it replaced. Learning adds one fit when the feedback files change (a few milliseconds for hundreds of reports), cached until they change again.

## Where it fails

- **Noise from strong general skills.** `application-security-testing` joins many "write tests" selections as a second job, because it is a strong "testing" match that also covers security. A report of `unhelpful` for those words removes it.
- **Single words.** "Roll out the new version" can add `mem-version-bump` on the word "version".
- **Vocabulary gaps.** Search is keyword-based, so a task that shares no words with the right skill misses it until feedback teaches the association. On the held-out tasks: "build the settings screen" in an iOS project and "write tests for the resource" in Quarkus (it picks `quarkus-verification`, not `quarkus-tdd`).
- **The project counted twice.** The words signal also searches with the project's technologies added, and the project has its own signal too. A skill named after the stack can then pass for one the task asked for: "add an accessible signup form" in a React project puts `react-three-fiber` first, a 3D library, because "react" is in its name. Restricting the project terms to skills the task's words already found removed that, left the dev sets unchanged, and dropped the held-out hit rate from 86% to 64%, because the same search is what finds `golang-testing` for "write tests" in a Go project. It was reverted. `select --explain` shows this case, and `--exclude react-three-fiber` with an `unhelpful` report corrects it for those words.
- **Feedback quality.** The model trusts what it is told. Reports that are wrong or lazy teach the wrong thing, within the damping and fading described above.
- **Not measured:** long-run use with real feedback, and whether the finished work is better.

## What to build next

1. **A task-outcome benchmark** with no skills, all skills, the hive without learning and with it, graded on finished work. Without it, every figure here is about choosing skills, not results.
2. **Embeddings for the words signal**, kept local, to close vocabulary gaps. It is one more independent signal, so the agreement rule already knows how to use it.
3. **Exploration.** Occasionally offer the second-best skill, marked as a trial, so feedback can reach skills the hive never picks. Today a skill that is never chosen can never be judged except by a "missing" report.
4. **Implicit feedback** from the agent: which chosen skills it opened, and whether tests passed after. Weak, but plentiful.
5. **Team learning**: share the model, not the logs, across a team, with opt-in and the same bounds.
6. **Hashed word pairs** if the log grows large enough that the feature count matters.

## Using it

```bash
python3 mcp/sfp_hive.py select "add an endpoint to list orders" --project .
python3 mcp/sfp_hive.py select "harden the API" --project . --goal "ship to production" --after api-design --json
python3 mcp/sfp_hive.py feedback last --helped rails-patterns --unhelpful test-collaboration --missing api-design
python3 mcp/sfp_hive.py status
python3 mcp/sfp_hive.py forget
python3 mcp/sfp_hive.py select "write tests" --project . --engine v1     # the earlier engine
python3 mcp/sfp_hive.py select "write tests" --project . --no-learning   # ignore what was learned
python3 mcp/sfp_hive.py evaluate
python3 mcp/sfp_hive.py learning-curve
```

From an installed skill, use `scripts/select_skills.py` inside the `sfp-hive` folder with the same arguments. Over MCP, `select_skills`, `give_feedback`, `learning_status` and `predict_next`. Data lives in `~/.sfp` (or the folder of `$SFP_USAGE_LOG`): `decisions.jsonl` and `feedback.jsonl`.

The product thinking (who would pay, and for what) is in [PRODUCT.md](PRODUCT.md).
