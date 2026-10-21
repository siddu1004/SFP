# The SFP Manager

> Since version 2.0.0 the manager runs on [the hive](HIVE.md), a colony algorithm that builds on the engine described here (now called v1). This page still describes v1's scoring, which the hive reuses for quality, and the product thinking.

The manager decides which skills an agent uses, when, and in what order. It is the `sfp-manager` skill, backed by the stack engine in `mcp/sfp_stack.py`, and it is also available as the `recommend_stack`, `predict_next` and `record_usage` MCP tools.

This page explains the idea, the algorithm, what has been measured, where it fails, what to build next, and how it could become a product.

## The idea: skills are filters

A photo filter does one thing. A good edit stacks a few in the right order: correct the exposure, then the colour, then sharpen. Stacking every filter in the app ruins the photo.

Skills behave the same way. One skill gives the agent one way of working. A short, ordered stack gives a better result. Loading many at once costs context, slows the agent and gives it conflicting instructions. The manager's job is to build the short stack.

| Filter idea | In the manager |
|---|---|
| A filter | A skill |
| A preset (a saved stack) | A recipe in `mcp/stack_recipes.json`, such as `ship-a-service` |
| Order matters | Skills are ordered by phase of work: research, plan, design, build, debug, test, secure, review, optimize, document, ship |
| Base adjustments, then looks, then a final check | Layers: `base` does the work, `check` verifies it, `finish` ships it. A named visual style acts as a look on top of the base |
| Two looks fight each other | At most one named visual style, and one skill per category and phase |
| Too many filters ruin the photo | A token budget (12,000 by default) and a cap of 4 skills |
| Your favourite presets | The usage log: what you used, in what order, and whether it helped |

## How it decides

```text
task words ───┐
project files ├─> candidates ─> score each ─> pick a stack ─> order by phase ─> stack + likely next
goal / phase  │                 (weighted)    (greedy, budget,
skills so far ┘                                no repeats, no clashes)
```

### 1. Read the situation

- **Task.** The user's words, with filler verbs ("add", "write", "use") dropped so "add tests" is about tests. Common synonyms are joined ("accessible" and "accessibility", "auth" and "authentication"), and two-word names become one ("Spring Boot", "Next.js").
- **Project.** A fingerprint from the files: `package.json` dependencies, `requirements.txt` and `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml` and Gradle files, `pubspec.yaml`, `composer.json`, `Gemfile`, Dockerfiles, Kubernetes charts, CI workflows, config files such as `next.config.*` and `playwright.config.*`, and the mix of file types. Frameworks weigh more than languages, and a framework implies its language (Django implies Python). It skips `node_modules`, virtual environments, build output and similar folders, and stops after 5,000 files.
- **Goal.** The phase of work the words point to, as a distribution: "write tests" is all test, "design the API and deploy it" is plan, build and ship.
- **History.** The skills already used in this session.

### 2. Score every candidate

Candidates come from three places: a search on the task words, a search on the task words plus the project's main technologies, and the Markov chain's predictions after the last skill used.

Relevance to the task is the base of the score. Every other signal multiplies it, so a skill that fits the project but not the task can never beat one that fits the task:

```text
score = relevance
      x (1 + 0.3 x category fit)          the task's words point at this skill's category
      x (0.85 + 0.3 x phase fit)          cosine between the task's phases and the skill's
      x (1 + 0.5 x project fit)           the skill's technology is in the project (general skills count as 0.6)
      x (1 - 0.6 x wrong technology)      the skill is for a technology the project does not use
      x (1 - 0.2 x unasked technology)    no project, and the skill is for one technology nobody named
      x (1 + 0.3 x Markov probability)    it usually follows the last skill used
      x (1 + 0.4 x past outcome)          it helped, or did not, the last times
```

### 3. Pick the stack

Greedy selection with maximal marginal relevance:

1. Keep only skills that share a word with the task and are not for the wrong technology.
2. Take the best one. Then repeatedly take the one with the best score minus 0.5 times its overlap with what is already chosen (overlap counts names as much as descriptions).
3. Skip a skill that takes a role already filled (same category and phase), that adds a second visual style, or that would go over the token budget.
4. Stop at 4 skills, or when the next best scores under 45% of the first.

Then order the stack by phase, label each skill's layer, and say why each one is there.

### 4. Predict what comes next

A first-order Markov chain over skills:

```text
P(b | a) = lam x c(a, b) / c(a)  +  (1 - lam) x back-off(b | a)
lam      = c(a) / (c(a) + number of distinct skills seen after a)      (Witten-Bell)
back-off = 0.5 x P(category of b | category of a) / size of that category
         + 0.5 x P(phase of b | phase of a) / number of skills in that phase
```

Counts come from the recipes (each step counts twice) and from your recorded usage. When a skill has a lot of history, its own counts dominate. When it has little, the prediction falls back to what usually follows its category and its phase of work. Unseen category pairs get a prior in proportion to category size, so a one-skill category is not over-predicted. Every row is normalized to sum to 1; a test checks it.

Outcomes ("helped", "unhelpful") give each skill a Beta(1 + helped, 1 + unhelpful) posterior. Its mean, centred on zero, is the outcome signal in the score.

## What it does well, measured

`python3 mcp/sfp_stack.py evaluate` reproduces these, and the README's copy of them is regenerated on every sync. The tests fail if they get worse. Figures at the time of writing:

| Measure | Stack engine | Plain search, same number of results |
|---|---:|---:|
| 91 tasks without a project: the right skill is in the stack | 89% | 85% |
| The top pick is right | 80% | 76% (search's first result) |
| 24 tasks in 10 fake projects: the right skill is in the stack | 79% | 29% |
| Stacks holding a skill for the wrong technology (of 24) | 0 | 1 |
| Skills per stack, on average | 2.0 | |
| Instructions loaded per task, on average | about 4,400 tokens | |
| Time to decide, on average | about 11 ms | |

The project result is the point of the manager. Given "write tests for the order view", plain search returns the same skills for every project. The manager returns `react-testing` in a Next.js app, `django-tdd` or `python-testing` in Django, `golang-testing` in Go and `rust-testing` in Rust.

**How much to trust these numbers.** The weights were tuned on the 91 search tasks, so the first two rows are optimistic. The 24 project tasks were written after tuning and scored once. After that I fixed one bug: when the top candidate was for the wrong technology, it set the cut-off and could empty the whole stack. The score stayed at 79%. The tasks and the correct answers were written by one person. Nothing here measures whether the agent's finished work is better.

## Where it fails

- **Vocabulary gaps.** The search is keyword-based. "Make the landing page feel premium" does not reach `design-taste-frontend`, because they share no words. Embeddings would fix most of these.
- **Rare words with no project.** "Add tests for the checkout flow" in an empty folder ranks `kotlin-coroutines-flows` first, because "flow" is a rare word. With a project, it is right.
- **Predictions with little data.** Before you record usage, predictions outside the recipes are generic: they follow the category and phase averages.
- **Generic tasks with no project.** "Containerize and deploy the service" in an empty folder puts `quarkus-verification`, a Java skill, first. In a Go project it gives `docker-patterns`. A stronger penalty for technologies nobody named was tried and did not help overall, so it stays as is.
- **Background skills slip in.** In a Django project with Celery, "write tests for the order view" also stacks `django-celery`, because its description mentions tests.
- **The phase vocabulary is hand-written**, and in English.
- **The fingerprint reads files, not code.** It knows a project uses React from `package.json`, not that the file you are editing is a server route.

## What to build next

In order of value for effort:

1. **A task-outcome benchmark.** Run real tasks with no skills, with all skills, and with the manager's stack, and grade the results. This is the claim the product rests on, and it is not measured yet.
2. **Embeddings for retrieval**, kept local (a small model, or precomputed vectors shipped in the repo), blended with the keyword score. This targets the biggest measured failure.
3. **Learn the weights from outcomes.** Once the log holds enough "helped" and "unhelpful" events, fit the weights with a simple learning-to-rank model instead of hand-tuning.
4. **A contextual bandit for stack choice.** Thompson sampling over close alternatives, so the manager sometimes tries the second-best skill and learns whether it is better. The Beta posteriors already exist.
5. **A hidden Markov model over phases.** The phase of work is the real hidden state; skills are what you observe. An HMM would infer "we are now testing" from the sequence, and predict the next phase as well as the next skill.
6. **Variable-order chains** (prediction by partial matching) once usage logs are long enough, and chains conditioned on project type, since a Django team's sequences differ from a Flutter team's.
7. **File-level context.** Use the file being edited, not only the project, so a route file and a component file in one repo get different stacks.

## Making it sellable

### What is worth paying for

The skills themselves are free and open, and most are other people's work under MIT or Apache-2.0. Reselling them is not a business, and it would rightly annoy their authors. What people would pay for is the judgement layer: picking the right few skills for this task in this codebase, and showing that it worked.

### Who pays, and why

| Customer | Pain | What they get |
|---|---|---|
| Individual developer | The agent gets slower and vaguer as skills pile up | Free: the manager, recipes, local learning |
| Team lead | Every developer's agent works differently; reviews catch the same mistakes | Shared team stacks ("how we ship a service here"), required checks such as `security-review` before any ship stack |
| Platform or DevEx team | Hundreds of internal and public skills, no idea which help | Usage and outcome analytics per skill and stack, private skills indexed beside public ones, a way to retire skills that never help |
| Regulated company | Agents must follow compliance steps | Compliance stacks (for example HIPAA or SOC 2 checks) that the manager always adds for matching tasks, with an audit log |
| Skill authors | Hard to get a skill found and trusted | A marketplace of stacks ranked by measured outcomes, with revenue share on paid packs |

### Product shape

1. **Open core (today).** Engine, recipes, router, MCP server, local learning. Free, MIT. This is the distribution channel.
2. **Team.** A shared stack registry synced to every IDE, team recipes, policies (always include, never include), private skill sources, aggregated outcomes. Per seat.
3. **Marketplace.** Creators publish stacks, like preset packs for photo apps: "Stripe payments stack", "Next.js SEO stack". Ranked by outcome data, not stars.
4. **Enterprise.** Self-hosted registry, SSO, audit logs, compliance stacks, support.

### Why it could hold up

- **Outcome data.** Which stacks actually helped, for which project types, is data nobody else has. It improves the ranking, which brings more use, which brings more data.
- **One manager across IDEs.** Teams use several agents. A manager that works the same in Claude Code, Cursor, Codex and the rest is more useful than any one vendor's.
- **Proof.** The evaluation harness already publishes its own numbers. Extending it to task outcomes would make the claims checkable, which most tools in this space cannot offer.

### Risks, stated plainly

- **The IDEs may build this in.** Claude Code already picks skills by description. The answer has to be better choices across IDEs, team policy and outcome data, not routing alone.
- **The quality gain is not yet proven.** Until the task-outcome benchmark exists, the honest claim is "fewer, better-matched skills, measured", not "better code".
- **Privacy.** Usage data is only valuable if teams trust it. Keep it local by default, send only skill names and outcomes when a team opts in, and never send prompts or code.
- **Licenses.** Paid packs must respect each skill's license and credit its authors. Recipes reference skills rather than copying them.

### First steps to test the business

1. Run the task-outcome benchmark and publish the result, good or bad.
2. Give five teams shared stacks and policies, and measure how often they accept a stack and how often they mark it as helping.
3. Ask ten skill authors whether they would publish stacks, and what would make them trust the ranking.
4. Price the team tier only after those numbers exist.

## Using it

```bash
python3 mcp/sfp_stack.py recommend "add tests for the checkout form" --project .
python3 mcp/sfp_stack.py recommend "harden the API" --project . --goal "ship to production" --after api-design
python3 mcp/sfp_stack.py next api-design
python3 mcp/sfp_stack.py record api-design --outcome helped
python3 mcp/sfp_stack.py profile .
python3 mcp/sfp_stack.py recipes
python3 mcp/sfp_stack.py evaluate
```

From an installed skill, use `scripts/stack.py` inside the `sfp-manager` skill folder with the same arguments. Over MCP, call `recommend_stack` with `task` and `project_path`.

The usage log is `~/.sfp/usage.jsonl` (or `$SFP_USAGE_LOG`). It holds skill names, times, session ids and outcomes, never prompts or file contents. Set `SFP_NO_USAGE_LOG=1` to turn recording off. Delete the file to forget everything.

To add a recipe, add an entry to `mcp/stack_recipes.json` with a `name`, a `goal` in plain words and the ordered `skills`. The tests check that every skill exists.
