# Pushing bundles

When a task fits a bundle, the hive attaches the **whole bundle, in its order**, instead of a few loose skills. A bundle is a tested sequence for one job, so a task that is "make the signup form accessible" gets design, accessibility and writing skills together, not one of them.

## How a bundle is matched (`sfp_library.match_bundles`)

Two kinds of evidence, combined:
- **Words** (65%): how much of the task's meaning the bundle's name, goal, when-to-use and skill names cover. Rarer words count more, and words no skill uses are ignored.
- **The hive's own choice** (35%): how many of the bundle's skills the hive picks on its own for this task.

From a score of 0.45 a bundle is **suggested** (listed, the rest of it preloaded). From 0.6 it is **pushed**: every skill joins the stack, in the bundle's order, even past the usual limit of four. A low limit set on purpose (below 3) is respected and nothing is pushed. A skill you removed stays out of a pushed bundle.

`sfp_hive.py select` takes `--bundles push` (the default), `suggest` or `off`. The result carries `bundles` (best first, each with `score`, `push`, `applied`, `missing`, `why`) and, when one was attached, `bundle: {id, name}`. `live` and the MCP `select_skills` do the same, and `live` keeps the pushed bundle steady while you keep typing the same idea.

## How well it matches

Labelled tasks: `tests/bundle_dev.json` (28, with 4 that fit no bundle) and `tests/bundle_heldout.json` (12, written before the matcher was tuned).
- Dev: right bundle first for 21 of 24 tasks (88%), pushed whole for 18 (75%), no false pushes.
- Held-out: right bundle first for 5 of 10 (50%), pushed whole for 5, no false pushes. This is the honest number for a task nobody tuned for; a task with no shared words (for example "reduce token usage in my agent prompts" against "Cut tokens") is missed.

Precision is high and recall is modest, on purpose: a wrong whole bundle is worse than a missing one. The next step is to learn from `give_feedback`: a bundle that was pushed and kept is a vote for it, one removed is a vote against.

## Brief for Antigravity

- In Choose and in the live chips, when `bundle` is set, show one banner "Bundle: <name>" above the skills, with the skills in order as numbered chips and a "Not this bundle" button that sends `exclude` for the bundle's skills. When only `bundles[0]` is suggested (`push` false), show "Looks like <name>" with an **Attach whole bundle** button (it calls the existing `select --bundle <id>`).
- Show `preload` skills greyed under the stack.
- Tests: a message-handler test for each button and a rendering test with escaping.
