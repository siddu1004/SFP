# Does it change the agent?

This page reports two small experiments that compare an agent working from its own knowledge with the same agent after the hive picked skills for the task. They are small, and one of them found nothing. Both are described as they ran.

## How it was run

Each task was given twice to a fresh agent (Claude Sonnet): once plain, and once with the skills that `sfp-hive` chose for that task and project, which the agent was told to read first. The plain agent was told not to read skill files. The checklists were written before any agent ran. Each is seven yes/no items, taken from the task itself or from the skill's own source documents. One run each, so a single sample per cell.

## Round 1: common engineering tasks

Five tasks where good practice is widely known: a Django avatar upload, Go table-driven tests, a Flask security review, an accessible React signup form, a paginated FastAPI endpoint. Answers were shuffled and unlabelled, and a separate agent graded each pair.

| Task | Plain | With skills |
|---|---|---|
| Django avatar upload | 7 | 6 |
| Go table-driven tests | 7 | 7 |
| Flask security review | 7 | 7 |
| React signup form | 7 | 7 |
| FastAPI paginated list | 7 | 7 |

**No difference in the score.** A strong model already knows these practices, so the checklist is at its ceiling. The Django gap is a grading call: the skill-guided answer reported upload errors as flash messages instead of rendering them in the form.

The answers did differ in approach, which the checklist does not measure. With skills, the agents followed the skill's project layout (a service layer and a typed dependency alias in FastAPI), wrote tests before the implementation (Django), re-encoded uploaded images to strip metadata, used `errors.Is` with sentinel errors, and added a fuzz test and a benchmark (Go). They also dropped skills that did not apply: one said a design skill "mostly does not apply" to a Django template, and another set aside an MCP-widget skill for a React form. Those two were the hive's mistakes: the selection for each task had one off-target skill out of two or three.

## Round 2: tools the model cannot know from training

Three tasks about programs that are in this library: OmniRoute with Codex, FreeLLMAPI, and Strix. The checklist came from each project's own documentation.

| Task | Plain | With skills |
|---|---|---|
| FreeLLMAPI: run it and call it with the fastest routing | 0 of 7 | 7 of 7 |
| OmniRoute: point Codex at it, start at login | 4 of 7 | 4 of 7 |
| Strix: non-interactive scan with a $10 budget | 6 of 7 | not scored |

Graded by the author against the written checklists, because every item is a literal command or value.

- **FreeLLMAPI is the clear difference.** The plain agent said it did not know the project and gave placeholders for the repository, the port and the routing option. The skill-guided agent gave the installer one-liner, port 3001, `base_url`, the `auto:fast` model, the unified key and the `x-routed-via` header. This is the case skills are for: knowledge the model does not have.
- **Where the model already knew the tool, there was little gain.** It knew most of Strix, and missed only the `--max-budget` flag, which it said did not exist. The skill-guided Strix run refused (the agent declined to write a pentest walkthrough), so there is no comparison. That says nothing about the skill.
- **OmniRoute tied.** The hive chose one skill, `config-codex-cli`, which does not contain the profile settings or the autostart command. The skill that does (`cli-setup`, with `omniroute autostart enable`) was not chosen, because the task says "starting at login" and that skill says "autostart". This is the miss the feedback loop exists for: reporting `cli-setup` as `missing` for this kind of task teaches the hive to offer it next time.

## What the experiments found in the hive

The FreeLLMAPI run first got the wrong skills. The skill is tagged with the one technology it mentions, Docker, and a task that said "Python SDK" made the project look Python-only, so the hive ruled it out as a technology mismatch. Tools that sit beside any language (Docker, Kubernetes, Terraform) no longer count as a mismatch. The accuracy on every evaluation set is unchanged, and a test covers the case. With the right skill the answer scored 7 of 7. The table above shows that second run.

## What this does and does not show

- Skills made a measurable difference where the agent lacked the knowledge, and a visible difference in approach where it did not. They did not raise the score on tasks the model already does well.
- Five plus three tasks, one run each, one model. This is evidence, not a benchmark. Run-to-run variation can be as large as the differences above.
- The skill-guided agent had a longer prompt, and no run controlled for that.
- To make the standing instruction matter, `install.sh rules --project .` tells the agent to use the hive at the start of each substantial task. Without it, installed skills help only when the agent decides to reach for them.
