# Needs: what a task requires beyond the model

A model cannot make a 3D mesh, open a web page, draw a picture, see the page it built, remember last week, or keep going once its limit runs out. A good skill list for "turn this photo into a 3D model" is not only skills about 3D: it must know the model needs an image-to-3D service, Blender and a key, and have them ready *before* the model gets stuck.

`capabilities.json` lists eight such abilities (3D from images or text, reading websites and platforms, never running out of tokens, finding a free API, generating media, checking work in a real browser, remembering earlier sessions, pentesting). Each names its trigger patterns, the provider skills in order of use, the programs it depends on (`apps/apps.json`) and any key it needs. `mcp/sfp_needs.py` does the rest:

- `sfp_hive.py needs "<task>" [--project P] [--check] [--json]` lists the needs of a task.
- `select`, `live` and the MCP `select_skills` tool now attach the first provider skill of every need (the model is told how to get unstuck) and list the rest under `preload`, to load before they are asked for. `select --no-needs` turns this off. The result carries `needs` and `preload`.
- `--check` also reports the state of each program (not installed, installed but not running, ready) and any missing key, and gives one `action`: the exact install or start command (`python3 apps/sfp_app.py install omniroute`). It runs the programs' `--version`, so it is never done while typing. Keys are only checked for presence, never read or stored.
- Installing stays a deliberate step: `sfp_app.py install ID` prints the plan and only runs it with `--yes`.

## How well it detects

Labelled tasks: `tests/needs_dev.json` (30, with 11 that need nothing) and `tests/needs_heldout.json` (20, written before the first run). On the first run the held-out set scored 19 of 20 exact (precision 1.0, recall 0.9); the miss ("scan our web app for sql injection") was then fixed in the rules, so the held-out set is now a floor and no longer an independent measure. Detection is regular expressions and costs about 0.1 ms.

## Limits

- Triggers are words. A task that needs a capability without using any of its words is missed; the feedback loop is not yet taught about needs.
- The project alone never creates a need; it only adds weight to one the task asks for.
- The same three-line `project` boost is all the project understanding that needs have. Using the project's dependencies (for example a `three` import) to preload before a task is typed is the next step.

## Brief for Antigravity

- In Choose and in the live chips, show each need as a card: the name, why, the attached skill, and the preload skills greyed. A card with `action` other than `ready` shows the command with Copy, and (after a confirm) a Run in terminal button that opens a terminal with the command and does not press Enter.
- Call `needs --check` when the user opens Choose or sends a message, never on each keystroke.
- Test: a message-handler test per new message and a rendering test with escaping.
