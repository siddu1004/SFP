# The Hive

The hive is the engine behind `sfp-manager`, in `mcp/sfp_hive.py`. It decides which skills an agent loads for a task, and in what order, using the rules a honeybee colony uses to divide work. This page covers the biology, the algorithm, the numbers, what went wrong on the way, and where to take it next.

## The biology, briefly

A colony has no manager. The queen lays eggs; she does not assign work. Thousands of bees still split the jobs of the hive well, and the mechanisms are well studied:

- **Nest-site selection** (Seeley, *Honeybee Democracy*, 2010). Scouts inspect sites independently and dance for good ones; better sites get longer dances and more recruits. Scouts for rival sites deliver stop signals to each other's dancers (Seeley et al., *Science*, 2012). The swarm commits when one site reaches a quorum of scouts.
- **Response thresholds** (Bonabeau, Theraulaz and Deneubourg, 1996; Theraulaz, Bonabeau and Deneubourg, 1998). Each worker has a threshold for each job. A job's need is a stimulus *s*; a worker with threshold *θ* takes it up with probability *s² / (s² + θ²)*. Working on a job reduces its stimulus. A worker that performs a job grows more sensitive to it, which produces specialists.
- **Stigmergy** (Grassé, 1959; Dorigo's ant colony optimisation, 1992). Ants coordinate through the environment: a used path gets pheromone, others follow strong trails, and pheromone evaporates, so the colony forgets routes that stop paying.

## The mapping

| Colony | Hive | Code |
|---|---|---|
| A possible nest site | A skill | `core.SKILLS` |
| A scout's judgement | One independent signal's vote, 0 to 1, or no opinion | `send_scouts` |
| Site quality | The task relevance, scaled by every other scout | `nectar` |
| Quorum | Strong task words (0.8 or more), or two scouts at 0.3 or more; never a skill for another technology | `has_quorum` |
| Stop signals | Each chosen skill lowers a rival's quality by 0.5 x their rivalry | `forage`, `rivalry` |
| Jobs in the hive | Phases of work: research, plan, design, build, debug, test, secure, review, optimize, document, ship | `v1.PHASE_ORDER` |
| A job's stimulus | 0.5 base need for every job, plus the share of the task that asks for it | `forage` |
| A worker's threshold for a job | 0.5 / (0.2 + 0.8 x the skill's affinity for that job), scaled by experience | `forage`, `affinity` |
| Taking a job | The job the skill responds to most; the stack takes it if the response is 0.2 or more, and the job's stimulus drops by 0.6 x the response | `forage`, `respond` |
| Specialisation | Each "helped" outcome multiplies the threshold by 0.85, each "unhelpful" by 1.15, within 0.5 to 2 | `Colony.threshold_scale` |
| Pheromone | Recorded skill-to-skill moves, weighted by 2^(-age / 30 days); recipes are permanent trails | `Colony` |
| Following trails | A Markov chain over the trails, smoothed by category and phase (Witten-Bell back-off), rows summing to 1 | `v1.Markov.prob` |

## The algorithm

```text
recommend(task, project, goal, skills used so far):
  1. read the situation
       words    the task's words, minus filler ("add", "write"), synonyms joined
       project  technologies from manifests and file types (scan cached 30 s)
       demand   share of each job the task and goal ask for
  2. send the scouts, for every skill the words or the trail can reach
       words     search relevance, normalised to the best match
       project   fit with the project's technology; no opinion for a general skill;
                 0 for another technology ("mismatch") or one nobody named
       role      cosine between the task's demand and the skill's jobs
       category  how much the task's words point at the skill's category
       trail     pheromone from the last skill used
  3. quorum: keep a skill only if its words are strong, or two scouts back it,
     and it is not for another technology
  4. quality = words x (1 + 0.3 category) x (0.85 + 0.3 role) x (1 + 0.5 project)
               x (1 + 0.3 trail), normalised so the best is 1
  5. forage, until four skills or nothing is left:
       left  = quality / experience - 0.5 x the strongest rivalry with any chosen skill
       take the skill with the most left; stop if nothing is left
       its response to each job = r(stimulus x left, threshold for that job)
       if the best response is under 0.2 (and something is already chosen), it stays in reserve
       if it would break the token budget (12,000 by default), it stays in reserve
       otherwise it takes that job, and the job's stimulus drops
  6. order the stack by phase; label base, check, finish; say who backed each skill
  7. follow the trails from the last skill to suggest what comes next
```

Rivalry between two skills is their similarity (names count as much as descriptions), plus 0.5 if they do the same job in the same category. So two near-identical MCP builders suppress each other strongly, while unit testing and end-to-end testing, which share a job but do different parts of it, can both stay.

## Results

`python3 mcp/sfp_hive.py evaluate` reproduces these, and the README's copy is regenerated on every sync. `tests/test_hive.py` fails if the hive falls below v1 or plain search on any set, below its floors, or ever stacks a skill for the wrong technology. Figures at the time of writing:

| Task set | Hive | v1 | Plain search |
|---|---:|---:|---:|
| 22 new tasks in 8 new projects (written before the hive, scored once) | 86% | 68% | 14% |
| 24 tasks in 10 sample projects | 79% | 79% | 33% |
| 91 tasks with no project | 89% | 89% | 86% |
| Top pick right, new tasks | 68% | 55% | |
| Skills per stack: no project / sample projects / new projects | 1.8 / 2.1 / 2.4 | 2.0 / 2.25 / 2.5 | |
| Stacks with a skill for the wrong technology, all sets | 0 | 0 | 2 |
| Time per decision, project already scanned | about 2 to 3 ms (7 ms in 2.0.0) | about 1 to 2 ms | |

Plain search gets about as many results as the hive's average stack.

**Why it does better on the new tasks.** Mostly the quorum. A skill that the task's words reach only together with the project's technologies is accepted when a second, independent scout (the project) backs it. That is how `rails-patterns` gets in for "add an endpoint to list orders" in a Rails app, where v1 picked unrelated gateway skills. A second rule in the hive, that a framework skill is plausible in a project showing only its language (SwiftUI in a `Package.swift` project), turned out not to matter: without it the new-task score is the same.

## How it was built, including what failed

The first versions were worse, and the reasons are useful.

1. **Continuous recruitment dynamics, one pool.** Support for each skill followed the cross-inhibition model of Seeley et al. and Pais et al.: discovery, waggle-dance recruitment, abandonment and stop signals, integrated over 40 steps, with all skills drawing on one pool of scouts. On the sample projects it found the right skill 58% of the time against v1's 79%. One shared pool is right for bees choosing one nest, but wrong for a stack that fills several jobs: the leader recruited nearly everyone, and a test skill crowded out a security skill.
2. **One pool per job.** Better (67%), but recruitment feedback was still winner-take-all inside a job: `react-testing` took 95% of the test pool and `e2e-testing`, its complement, 0.1%.
3. **Weaker rivalry, slower recruitment.** No better (63%). The phase vocabulary that defines jobs is hand-written and noisy, so letting it veto skills cost more than it gave.
4. **Base demand for every job, and the best option always goes out.** Stacks grew to 3.5 skills to match v1's hit rate. Bigger stacks hit more only because they are bigger.
5. **A grid search** over the dynamics' constants confirmed it: at equal stack size, the continuous dynamics stayed 2 to 8 points behind v1.
6. **The final design** drops the continuous simulation and keeps each mechanism where it helps: quorum as a filter, stop signals as a discrete penalty, and response thresholds to decide how many skills each job takes. A second grid search (36 settings, on the development sets only) gave a setting that matches v1's hit rate on both development sets with about 10% fewer skills. Then the new set was opened, once.

Two bugs were found and fixed on the way: v1 could recommend `sfp-manager` itself (it no longer can, and fixing it did not change v1's score), and the hive's "no skill took up" line listed every job.

## Where it fails

- **Noise from strong general skills.** `application-security-testing` joins many "write tests" stacks as a second job, because it is a strong "testing" match that also covers security.
- **Single words.** "Roll out the new version" adds `mem-version-bump` on the word "version".
- **Vocabulary gaps.** Search is keyword-based, so tasks that share no words with the right skill miss it, as in v1. On the new tasks: "build the settings screen" in an iOS project, "add a tool that creates tickets" in an MCP server, and "write tests for the resource" in Quarkus (it picks `quarkus-verification`, not `quarkus-tdd`).
- **Learning is shown, not measured.** Tests prove that outcomes change thresholds and choices, and that trails evaporate, but there is no long-run data yet on whether learning improves real sessions.
- **Not measured at all:** whether the finished work is better.

## Speed

Version 2.0.1 sped up every step without changing a single answer. Before and after, medians on the same machine (a shared cloud sandbox, so absolute numbers vary, the ratios are what to read):

| Step | 2.0.0 | 2.0.1 | What changed |
|---|---:|---:|---|
| Search the library | 0.4 to 0.6 ms | 0.08 ms | A word-to-skills lookup, so a query scores only the skills that share a word with it, not all 559 |
| Predict the next skill | 5 to 8 ms | 0.3 to 0.4 ms | Skills in the same category and job share one back-off value, computed once; the top few are picked without sorting everything |
| One decision, project already scanned | 7.5 ms | 1.8 to 2.8 ms | The two changes above, plus a per-skill cache of its main job |
| Through the running MCP server, later calls | 15 to 27 ms | 3 to 5 ms | The same |
| MCP server, first call after start-up (client pauses half a second) | 47 to 55 ms | 5 to 9 ms | The hive is loaded in the background while the client starts |
| One-shot command line call on this repo | 167 to 180 ms | 125 to 129 ms | The saved search index, a faster start-up, and the above |
| Scan a project of 1,495 files | 28 to 40 ms | 27 to 41 ms | Unchanged: it is mostly the cost of walking the folders |

How, in order of effect:

1. **Faster prediction.** The Markov back-off depends only on the category and job of the two skills, so it is computed once per group (a few hundred) instead of once per pair (over 55,000 per decision). This was the largest single cost.
2. **A lookup instead of a full scan** for search, built from the same index.
3. **A saved search index.** The sync writes `index.json`; start-up loads it instead of tokenizing 559 descriptions. It is used only if its key matches the catalog and the tokenizer exactly, and is rebuilt otherwise, so a stale file can never change an answer.
4. **Cheaper start-up work.** Stemming is cached, the job vectors are built in one pass per skill instead of eleven, and `argparse` and `subprocess` load only when used.
5. **Warm-up.** The MCP server loads the hive in the background right after start, so the first real call is not the slow one.

What I tried to keep honest: before touching the code I recorded every engine's exact output on all 137 evaluation tasks, and after each change compared it byte for byte. All of them stayed identical. `tests/test_speed.py` now keeps this true: it checks each fast path against the plain definition it replaced (search against scoring every skill, prediction against scoring every pair, the saved index against a fresh build), and holds generous speed budgets, about ten times what a laptop needs, so only a real regression fails.

What did not get faster: scanning a large project. A scan of this repo (1,495 files in 846 folders) takes about 30 ms, which is now most of a one-shot call. The running MCP server caches it for 30 seconds, so it is paid once per project, not per call. Caching it on disk would risk serving stale results after a dependency edit, so I left it.

Most of the remaining time in a one-shot call is starting Python (about 20 ms) and loading the catalog (about 25 ms). The MCP server pays that once, when your IDE starts it.

## Embedded, not a middleman

The hive is a function call, not a service. The MCP server imports it, and the `sfp-manager` skill runs it in-process through its own script. A decision takes tens of milliseconds, and the project scan, the slowest part, is cached for 30 seconds. The skill tells the agent to ask once per phase of work, not for every message. When Python is missing, the skill lists the same rules in plain words (quorum, one or two per job, stop signals, order, stop at four), so the agent can apply them itself.

## What to build next

Ideas that stay close to the biology:

1. **Scouts that read meaning, not words.** A local embedding scout would close the vocabulary gaps, the largest measured failure. It is one more independent vote, so the quorum rule already knows how to use it.
2. **Age polyethism.** Young bees work inside, older ones forage. Skills could move through stages: a new skill starts as a reserve option and earns its place by recorded outcomes before it leads a stack.
3. **Energy budgets.** Foragers weigh the energy a flower costs against its nectar. The token budget could become a true cost-benefit term, so a 5,000-token skill must be worth more than a 700-token one to be chosen.
4. **Swarming.** When a colony grows too big, it splits. A task with too many jobs could be split into sub-tasks, each with its own stack and its own subagent.
5. **Negative selection, from the immune system.** A list of skills that must never run together, or never on certain projects, learned from "unhelpful" outcomes.
6. **A task-outcome benchmark** with no skills, all skills, v1 and the hive, graded on finished work. Without it, every number here is about choosing skills, not about results.

## Using it

```bash
python3 mcp/sfp_hive.py recommend "add an endpoint to list orders" --project .
python3 mcp/sfp_hive.py recommend "harden the API" --project . --goal "ship to production" --after api-design --json
python3 mcp/sfp_hive.py recommend "write tests" --project . --engine v1     # the previous engine
python3 mcp/sfp_hive.py next api-design
python3 mcp/sfp_hive.py record api-design --outcome helped
python3 mcp/sfp_hive.py evaluate
```

From an installed skill, use `scripts/stack.py` inside the `sfp-manager` folder with the same arguments. Over MCP, `recommend_stack` runs the hive and `predict_next` follows its trails. The usage log is `~/.sfp/usage.jsonl` (or `$SFP_USAGE_LOG`): skill names, times, sessions and outcomes, never prompts or code. `SFP_NO_USAGE_LOG=1` turns it off.

The product thinking from v1 (who would pay, and for what) still applies; it is in [MANAGER.md](MANAGER.md).
