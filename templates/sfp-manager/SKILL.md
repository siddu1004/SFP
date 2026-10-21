---
name: sfp-manager
description: Decides which SFP skills to use, when, and in what order. Use at the start of any substantial build, fix, test, review, security or deploy task, and again when the work moves to a new phase. It reads the task, the project files and the skills used so far, and returns a short ordered stack of skills to load instead of many.
---

# SFP manager: the right skills, at the right time

You have access to hundreds of SFP skills. Loading many at once slows you down and blurs the instructions. This skill picks the two to four that fit this task in this project, in the order to apply them, like a short stack of photo filters.

## 1. Get the stack

Run the engine from this skill's folder, with the user's own words and the project folder:

```bash
python3 scripts/stack.py recommend "<the user's task>" --project <project folder>
```

Add what you know:

- `--goal "<end goal>"` when the user wants more than the task, for example "ship it today".
- `--after skill-a,skill-b` with the skills already used in this session, most recent last.
- `--budget 6000` to keep the loaded instructions small for a quick task.
- `--json` for the full scores and evidence.

If the SFP MCP server is connected, call its `recommend_stack` tool instead, with `task` and `project_path`.

If Python is not available, use the `sfp` skill to search by hand, and pick at most one skill per role below.

## 2. Apply it in order

The stack is ordered by phase of work. Each line says the skill's layer:

| Layer | What it does | How to use it |
|---|---|---|
| `base` | Does the work: research, plan, design, build, debug | Read it first and follow it while you work |
| `check` | Verifies the work: tests, security, review | Apply it once the base work exists |
| `finish` | Gets it out: performance, docs, release | Apply it last, if the task goes that far |

Read each skill only when you reach its layer. Its file is at `<SFP>/<path from the stack>`; `<SFP>` is the folder in `~/.sfp/root`. Skills that are installed in your skill list can be invoked by name instead.

## 3. Re-plan when the work changes

Run `recommend` again when the user changes the goal, or the work moves to a new phase (from building to testing, or from fixing to shipping). Pass the skills already used with `--after`, so the engine can predict what comes next. To see the likely next skills directly:

```bash
python3 scripts/stack.py next <skill just used>
```

## 4. Teach it

After a skill was clearly useful, or clearly not, record it. This writes one line with the skill name and time to `~/.sfp/usage.jsonl` on this machine, and nothing else:

```bash
python3 scripts/stack.py record <skill> --outcome helped
python3 scripts/stack.py record <skill> --outcome unhelpful
```

Recorded sequences train the predictions, and outcomes nudge future stacks. Mention the file to the user once before you first record. `SFP_NO_USAGE_LOG=1` turns recording off.

## Rules

- Use the stack, not more. If the stack is empty, no skill fits well: say so and do the task normally.
- Trust the project fingerprint over your guess. If it reports the wrong technologies, name the right one in the task, for example "add tests in Django".
- A recipe line ("Matching recipe: ...") is a proven sequence for this kind of goal. Prefer it when the user wants the whole job done, not one step.
- Never load a skill for a different technology than the project's.
- Tell the user, in one line, which skills you are using and why.
