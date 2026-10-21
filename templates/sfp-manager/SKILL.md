---
name: sfp-manager
description: Decides which SFP skills to use, when, and in what order, the way a bee colony divides work. Use at the start of any substantial build, fix, test, review, security or deploy task, and again when the work moves to a new phase. It reads the task, the project files and the skills used so far, and returns a short ordered stack of skills to load instead of many.
---

# SFP manager: the hive

You can reach hundreds of SFP skills. Loading many at once slows you down and blurs the instructions. This skill picks the few that fit this task in this project, and the order to use them in.

It works like a honeybee colony. No bee is in charge; the queen does not hand out work. Instead:

- **Scouts and quorum.** Independent scouts judge each skill: the task's words, the project's technologies, the phase of work, the task's category, and the trail from the last skill used. A skill is chosen only with a quorum: strong task words, or at least two scouts in favour. One noisy signal cannot decide.
- **Stop signals.** Each skill chosen suppresses its rivals in proportion to how alike they are, so you never get two skills that do the same thing.
- **Response thresholds.** Every job (plan, build, test, secure, ship, ...) has a level of need. A skill takes the job it responds to most, and that job's need drops, so a job gets one or two skills and an unneeded job gets none.
- **Pheromone trails.** Recorded sequences of skills leave trails that predict the next skill. Old trails evaporate with a 30-day half-life.

## 1. Get the stack, once per phase

Run the hive from this skill's folder with the user's own words and the project folder. It takes tens of milliseconds and runs on this machine:

```bash
python3 scripts/stack.py recommend "<the user's task>" --project <project folder>
```

Add what you know:

- `--goal "<end goal>"` when the user wants more than the task, for example "ship it today".
- `--after skill-a,skill-b` with the skills already used, most recent last.
- `--budget 6000` to keep the loaded instructions small for a quick task.
- `--json` for every scout's vote and each skill's response to its job.

If the SFP MCP server is connected, call its `recommend_stack` tool instead, with `task` and `project_path`.

Call it once at the start and once each time the work moves to a new phase. Do not call it for every message: the stack holds until the job changes.

## 2. Apply the stack in order

| Layer | Its job | How to use it |
|---|---|---|
| `base` | Does the work: research, plan, design, build, debug | Read it first and follow it while you work |
| `check` | Verifies the work: tests, security, review | Apply it once the base work exists |
| `finish` | Gets it out: performance, docs, release | Apply it last, if the task goes that far |

Read each skill only when you reach its layer. Its file is at `<SFP>/<path from the stack>`, where `<SFP>` is the folder written in `~/.sfp/root`. Installed skills can be invoked by name instead.

"No skill took up: test" means the task needs that job and no skill was strong enough for it. Do that part with your own judgement, or ask the hive again with clearer words for it.

## 3. Without Python: the colony rules

If you cannot run the script, apply the same rules yourself, using the `sfp` skill's index to find candidates:

1. **Quorum.** Consider a skill only if the task's words name what it is for, and it suits the project's technology. Never take a skill for another framework than the project's.
2. **One per job.** Decide which jobs the task needs. Give each needed job its single best skill; add a second only if it does a clearly different part of that job.
3. **Stop signals.** Drop any skill that repeats one already chosen.
4. **Order.** Apply the skills from planning and building, to checking, to shipping.
5. **Stop at four.** Most tasks need one to three.

## 4. Teach the colony

After a skill clearly helped, or clearly did not, record it. This adds one line with the skill name and time to `~/.sfp/usage.jsonl` on this machine, and nothing else. Mention the file to the user once before you first record.

```bash
python3 scripts/stack.py record <skill> --outcome helped
python3 scripts/stack.py record <skill> --outcome unhelpful
```

"Helped" lowers that skill's threshold, so it is chosen sooner next time; "unhelpful" raises it. Recorded sequences lay the trails that `python3 scripts/stack.py next <skill>` follows. `SFP_NO_USAGE_LOG=1` turns recording off.

## Rules

- Use the stack, not more. If it is empty, no skill fits well: say so and do the task normally.
- Trust the project fingerprint over your guess. If it lists the wrong technologies, name the right one in the task, for example "add tests in Django".
- A "Matching recipe" line is a proven sequence for this kind of goal. Prefer it when the user wants the whole job done, not one step.
- Tell the user, in one line, which skills you are using and why.
