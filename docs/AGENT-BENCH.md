# Does SFP make the agent's code better?

SFP's own numbers measure selection: whether the right skill is in the stack (86% on 22 held-out tasks). This page
measures the next question: does the agent write better code with those skills? So far, on small tasks, it does not.

## Setup

- **Agent.** Claude Code in headless mode, isolated from everything installed on the machine: no plugins, skills,
  slash commands, MCP servers, hooks or user settings. Both arms have the same model, prompt and tools.
- **The only difference.** In the SFP arm, the workspace holds the rule file the SFP Hive extension writes for the
  task (as `CLAUDE.md`): the skills the hive chose, in order, and the `SKILL.md` file to read for each. The baseline
  has no rule file.
- **Five tasks**, each a one-line request on a small codebase, with checks the agent never sees:
  rate limiting (6 checks), a security review that should find SQL injection (6), a bug fix (5), an accessible
  signup form (8), and writing tests, scored by how many of 10 planted bugs the tests catch.
- **Two models**, Sonnet and Haiku, two runs per task and arm: 40 runs.
- Run it: `python3 bench/agent/run.py --model sonnet --reps 2`. Results: `bench/agent/results/`.

## Results (2026-10-25)

| Model | Arm | Checks passed | Cost per task | Time per task | Skill files read |
|---|---|---:|---:|---:|---:|
| Sonnet | without SFP | 100% | $0.053 | 15.6 s | 0 |
| Sonnet | with SFP | 100% | $0.136 | 20.8 s | 3.2 |
| Haiku | without SFP | 100% | $0.008 | 37.2 s | 0 |
| Haiku | with SFP | 100% | $0.014 | 35.5 s | 4.0 |

Every run in both arms passed every check. On tasks this size the models do not need skills, and reading them costs
about 1.7 to 2.6 times as much. The agent did read the skills it was given (3 to 4 files per run), so the rule file
works as a delivery mechanism.

## What it also showed

The hive's choice was right for two of the five prompts (the security review and the form) and wrong for three:
the rate-limiting prompt got skills for LLM rate limits ("429", "rate limit"), the bug fix got two n8n skills ahead
of the error-handling ones, and "write tests for cart.py" in a Python project got the Go service bundle. The wrong
skills did no harm here, because the model ignored what did not apply, but they cost tokens. These are open problems
in selection; the tasks were written before the hive's choices were looked at, and nothing was tuned on them.

One grader check was too narrow: the accessible-form check looked only for the original error element's id, and
failed a better fix (one error per field, linked with `aria-describedby`, announced with `role="alert"`). It was
widened to accept any announced or linked error and every run of both arms was graded again with it.

## What would show a difference

Tasks where the skill carries knowledge the model lacks or would skip: larger codebases with house conventions, a
framework release newer than the model, multi-step work (migrations, release checklists) where a checklist skill
prevents a missed step, and longer sessions where the agent would otherwise drift. That is the next set to write,
again before looking at what the hive picks for it.

## Design work over rounds (2026-10-25)

Your point about design: you re-prompt until a page looks right, so the measure is how many rounds that takes.
`bench/design/run.py` simulates it. The agent (Sonnet) builds a page; it is screenshotted at desktop and phone width; a
reviewer model (Opus) scores the screenshots against `bench/design/rubric.md` without seeing the code, the rule file or
which arm made it, and says whether it would ship. If not, its three requested changes go back to the agent as the
next prompt, for up to four rounds. Three pages: a pricing page, a notification settings page and the empty state of
an analytics dashboard. Three arms, two runs each: 18 runs.

| Arm | Shipped within 4 rounds | Rounds to ship (5 = never) | First-round score | Final score | Agent cost per run |
|---|---:|---:|---:|---:|---:|
| No skills | 4 of 6 | 3.67 | 6.5 | 7.5 | $0.73 |
| SFP's choice | **5 of 6** | **2.83** | 6.8 | 7.8 | $0.85 |
| Two design skills picked by hand | 4 of 6 | 3.67 | 6.3 | 7.8 | $1.42 |

With SFP's skills the pages reached "ship" in fewer rounds: 2.8 against 3.7, and 5 of 6 against 4 of 6. Read it with
care:

- Six runs per arm. One run more or less moves "shipped" by a sixth, so this is a signal worth testing at scale, not
  proof.
- The settings run that shipped in two rounds had poor skills (a Slack GIF skill, an MCP app skill), so not all of the
  gain can be the skills' content. The first SFP settings run did not ship either.
- The hand-picked design skills (impeccable, frontend-design) did not help here, cost the most (their instructions
  are long), and once broke the page's script in the first round.
- The three page prompts were also used to improve how SFP recognises design work (3.17.6), so they are not held out.

Next: more runs per arm, fresh prompts written before looking at SFP's choice, and a second reviewer model.
