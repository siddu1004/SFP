---
name: sfp-select
description: Chooses which SFP skills to use for a task, in what order, and learns from feedback. Use at the start of any substantial build, fix, test, review, security or deploy task, and again when the work moves to a new phase. It reads the task, the project's files and the skills used so far, returns a short ordered list of skills to load instead of many, and improves when you tell it what helped and what did not.
---

# SFP skill selection

SFP has hundreds of skills. Loading many at once costs context and blurs the instructions. This skill picks the few that fit this task in this project, and the order to use them in. It gets better when you report how each decision turned out.

## 1. Select

Run the selector from this skill's folder with the user's own words and the project folder. It takes a few milliseconds and runs on this machine:

```bash
python3 scripts/select_skills.py select "<the user's task>" --project <project folder>
```

Add what you know:

- `--goal "<end goal>"` when the user wants more than the task, for example "ship it today".
- `--after skill-a,skill-b` with the skills already used, most recent last.
- `--budget 6000` to keep the loaded instructions small for a quick task.
- `--json` for every signal and the full detail.

If the SFP MCP server is connected, call its `select_skills` tool instead, with `task` and `project_path`.

Call it once at the start, and again when the work moves to a new phase (from building to testing, or to shipping). Do not call it for every message: the list holds until the job changes. Keep the **decision id** it returns: you need it for feedback.

## 2. Apply the list in order

| Layer | Its job | How to use it |
|---|---|---|
| `base` | Does the work: research, plan, design, build, debug | Read it first and follow it while you work |
| `check` | Verifies the work: tests, security, review | Apply it once the base work exists |
| `finish` | Gets it out: performance, docs, release | Apply it last, if the task goes that far |

Read each skill only when you reach its layer. Its file is at `<SFP>/<path from the list>`, where `<SFP>` is the folder written in `~/.sfp/root`. Installed skills can be invoked by name instead. Tell the user, in one line, which skills you are using and why.

"No skill took: test" means the task needs that job and no skill was strong enough for it. Do that part with your own judgement, or select again with clearer words for it.

## 3. Give feedback when the task ends

This is how the selector learns from its mistakes. When the task is done, report how the decision went. Ask the user one short question if you are not sure: "Were these skills useful? Was one missing?"

```bash
python3 scripts/select_skills.py feedback last --helped django-tdd --unhelpful django-celery --missing python-testing
```

With the MCP server, call `give_feedback` with the same lists.

| Verdict | Use it when | What it teaches |
|---|---|---|
| `--helped` | A chosen skill clearly made the work better | Favour it for tasks with these words |
| `--unhelpful` | A chosen skill misled you or added nothing | Avoid it for tasks with these words |
| `--ignored` | A chosen skill was never opened or used | A weak signal against it |
| `--missing` | You needed a skill that was not chosen | Favour it for these words, and find it even when search misses it |

Only report what you actually observed. Do not mark a skill `helped` just because the task finished. A wrong report teaches the wrong thing, though no single report can ban a skill: the effect is strongly damped and fades over months.

Mention once, the first time, what is stored: skill names, verdicts, times, the project's main technologies and the stems of the task's main words (for example `test`, `order`, `view`), in `~/.sfp` on this machine. No sentences, no file contents, nothing leaves the machine. `python3 scripts/select_skills.py status` shows what it has learned; `forget` deletes it all. `SFP_LEARN_WORDS=0` stops recording words, and `SFP_NO_LEARNING=1` stops recording and learning altogether.

## 4. Without Python

If you cannot run the script, apply the same rules yourself, using the `sfp` skill's index to find candidates:

1. **Agreement.** Consider a skill only if the task's words name what it is for, and it suits the project's technology. Never take a skill for another framework than the project's.
2. **One per job.** Decide which jobs the task needs. Give each needed job its single best skill; add a second only if it does a clearly different part of that job.
3. **No overlap.** Drop any skill that repeats one already chosen.
4. **Order.** Apply the skills from planning and building, to checking, to shipping.
5. **Stop at four.** Most tasks need one to three.

## Rules

- Use the list, not more. If it is empty, no skill fits well: say so and do the task normally.
- Trust the project fingerprint over your guess. If it lists the wrong technologies, name the right one in the task, for example "add tests in Django".
- A "Matching recipe" line is a proven sequence for this kind of goal. Prefer it when the user wants the whole job done, not one step.
- Give feedback once per task, when it ends. Do not ask the user for feedback in the middle of the work.
