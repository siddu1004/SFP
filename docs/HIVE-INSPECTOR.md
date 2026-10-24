# Hive Inspector: a visible button to see, judge and steer the skill choice

This is the build brief for a button by the agent window that shows which skills the hive chose, lets you judge how it chose them, and lets you change the choice. It is written as a prompt for Antigravity's agent, followed by how to evaluate the result.

## What is already done

The hard part is in place and tested, so the agent only builds the interface:

- `python3 mcp/sfp_hive.py select "<task>" --json --explain` returns the chosen skills and an `explain` list: the top candidates, each with its five signal votes (words, project, role, category, history), the signals that backed it, its learned preference, its token cost, and a `status` saying why it was chosen or dropped (`chosen`, `pinned by you`, `excluded by you`, `dropped: no agreement ...`, `dropped: overlaps a chosen skill`, `dropped: over the token budget`, `dropped: not reached: the stack was full`, `dropped: for another technology than the project`).
- `--exclude a,b` rules skills out and `--include c` pins skills in. The answer then has `intervention: {pinned, excluded}` and pinned skills carry the reason `pinned by you`.
- In the extension, `src/hive.ts` has `selectArgs(root, task, project, max, {include, exclude, explain})`, the `Candidate` and `Steer` types, and `interventionFeedback(before, steer)`, which turns an intervention into feedback (a chosen skill you removed is `unhelpful`; one you added is `missing`).

## Where the button can go

The circled area, the agent window's input bar, belongs to Antigravity. No documented way exists for an extension to add a button there, and VS Code's own guidelines say an extension cannot place a view directly in the secondary (right) side bar, though the user can drag one there ([sidebars](https://code.visualstudio.com/api/ux-guidelines/sidebars.md), [views](https://code.visualstudio.com/api/ux-guidelines/views.md)). So the brief asks the agent to look for a supported hook first, and otherwise use the closest supported places:

1. A status-bar item on the right, which sits directly under the agent window: an icon and a count, such as `Hive 3`, always visible.
2. The SFP Hive view, which you drag into the right side bar under or beside the agent window once. The editor remembers the layout.
3. A button in the editor title bar.

## The prompt

Paste this into Antigravity's agent with the SFP checkout open. It works in stages and stops for you to check each one.

> Build the "Hive Inspector" in the SFP Hive extension at `extensions/antigravity-hive/`. Read `docs/HIVE-INSPECTOR.md`, `docs/ANTIGRAVITY.md`, `extensions/antigravity-hive/src/hive.ts` and `src/extension.ts` first. Rules for the whole job: do not read, copy or modify Antigravity's own installed files; use only the public VS Code extension API; add no runtime dependencies; keep every call to the hive in `src/hive.ts`; keep `npm test` passing and add tests for everything you add. Work in the stages below and stop after each one with a short report of what you did and what I should look at.
>
> **Stage 1, find the hook.** Find out whether Antigravity lets an extension add a button or text to the agent window's input bar. Use only public routes: run a temporary command in the extension that logs `vscode.commands.getCommands(true)` filtered by "agent", "chat", "antigravity" and "cascade"; check the keyboard shortcuts list; read Antigravity's own documentation. Report what you found, and whether any command accepts a prompt string. Remove the temporary command. Do not continue to stage 2 until I answer.
>
> **Stage 2, the button.** Add a status-bar item on the right (`StatusBarAlignment.Right`, high priority) with the hexagon icon and the number of chosen skills, `Hive` when nothing is chosen. Clicking it opens the Inspector. Keep the existing left item or replace it, whichever I choose in stage 1. If stage 1 found a supported hook in the agent window, also put the button there. Add an editor-title button that opens the Inspector.
>
> **Stage 3, the Inspector.** A webview (a `WebviewView` in the SFP Hive container, so I can drag it next to the agent window) with:
> 1. A task box and a Choose button. It calls the hive with `explain: true`, and prefills from the editor selection if there is one.
> 2. **Chosen**: one card per skill, in order, grouped as Base, Check and Finish. Each card shows the name, phase, score, tokens and reasons, and has buttons for Open, Remove, Helped, Unhelpful and Ignored.
> 3. **Considered but not taken**: a table from `explain`, with the name, the status reason in plain words, five small bars for the signal votes (an empty bar when a signal abstained), the backers and the learned preference, and an Add button on each row.
> 4. **Add any skill**: a search box over `catalog.json`.
> 5. **Re-choose with my changes**: re-runs with the current include and exclude lists, then shows what changed against the previous run (added in green, removed in red).
> 6. **Apply**: builds the prompt from the final stack with `buildPrompt` and copies it, or sends it to the agent window if stage 1 found a supported way.
> 7. **Learning**: when I apply a stack I changed, send the feedback from `interventionFeedback` for the original decision. Show it first with a "Send this feedback" checkbox that is on by default.
> 8. **This session**: decisions made, how many I changed, the share of chosen skills I kept, the skills I added, and helped versus unhelpful. Keep these counts in the extension's `workspaceState`.
>
> Build the webview to the editor's standards: a content security policy with a nonce, no remote scripts, styles or fonts, every piece of text escaped, colours from the editor's theme variables (`var(--vscode-...)`), and keyboard access to every button.
>
> **Stage 4, tests.** Unit tests for any new pure functions in `src/hive.ts`, such as the diff between two selections and the session counters. In `test/extension.test.js`, extend the stand-in `vscode` with what the webview needs and test that the Choose, Remove, Add, Re-choose and Apply messages call the hive with the right arguments. Extend `test/e2e/drive.js` to click the status-bar item, choose, remove one skill, add one, re-choose, apply, and check the feedback log. Run `npm test` and `python3 -m unittest discover -s tests` from the checkout, and show me the totals.
>
> **Stage 5, check it in this editor.** Run `python3 extensions/antigravity-hive/install.py`, ask me to reload the window, then walk me through checks I1 to I10 in `docs/HIVE-INSPECTOR.md` one at a time, and write the report as a table.

## Checking the build

| ID | Do | Expected |
|---|---|---|
| I1 | Look at the status bar, right side, after a reload | The hexagon icon and `Hive` |
| I2 | Click it | The Inspector opens |
| I3 | Choose for `write table driven tests for a go parser` in a Go project | Cards for the chosen skills, grouped by layer; the count in the status bar matches |
| I4 | Look at "Considered but not taken" | At least five rows, each with a reason and five signal bars |
| I5 | Remove a chosen skill and add one from the table, then Re-choose | The removed skill is gone, the added one shows "pinned by you", and the change is shown in red and green |
| I6 | Apply | The prompt is copied, or appears in the agent window, and lists the final stack |
| I7 | Check `~/.sfp/feedback.jsonl` | New lines: `unhelpful` for the removed skill and `missing` for the added one, both with the original decision id |
| I8 | Choose the same task again | The removed skill is lower or gone, because the hive learned from I7 |
| I9 | Use the Inspector with the keyboard only, then switch to a light theme | Everything can be reached, and every part follows the theme |
| I10 | Run `npm test` and `python3 -m unittest discover -s tests` | Both pass |

## Evaluating the choosing process

The Inspector makes the choice visible. These numbers show whether it is any good. Count them over at least 20 real tasks; the session panel in stage 3 keeps most of them.

| Measure | How to count it | What good looks like |
|---|---|---|
| Kept | Chosen skills you did not remove, divided by all chosen skills | High, and rising |
| Top choice accepted | Decisions where you kept the first skill | High |
| Intervention rate | Decisions where you changed anything | Falling over time |
| Missing per decision | Skills you added, divided by decisions | Low, and falling |
| Helped share | Helped, divided by helped plus unhelpful | High |
| Dropped wrongly | Times a skill you added was in "Considered but not taken" | Shows which rule dropped it: the status reason names it |

Compare the first ten tasks with the last ten. If kept rises and the intervention rate falls, the hive is learning from you. If a status reason keeps naming the same rule, for example "no agreement" for skills you then add, that rule is too strict for your work, so send the examples back for a fix. A known case to start with: in a React project, "add an accessible signup form" puts `react-three-fiber` first. `docs/HIVE.md` explains why, and removing it once in the Inspector is the intended correction.
