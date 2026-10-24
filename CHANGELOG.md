# Changelog

## 3.5.0

- **The hive as an extension for Antigravity and other VS Code editors** (`extensions/antigravity-hive/`, TypeScript, MIT). A status-bar item and an activity-bar view choose the skills for a task, group them as base, check and finish, copy a ready prompt for the agent panel, open each skill, and record `helped`, `unhelpful`, `ignored` and `missing` feedback. Commands open the installer for skills, the standing instruction and programs such as OmniRoute, showing the plan first. `install.py` in that folder builds the `.vsix` and installs it with the editor's own command. 18 tests, including a real end-to-end run of the hive. It has not been run inside Antigravity itself. `docs/ANTIGRAVITY.md` explains the design, why it is an extension and not a patch to the editor, and has seven implementation prompts for extending it.
- **Five more sources:** react-three-fiber, liquid-glass-js, shadergradient and liquid-logo as frontend skills with each project's docs and source, and Graphify (Apache-2.0) as a research skill plus a program entry (`uv tool install graphifyy`).
- The dev-set floor against the earlier engine allows one task of slack, since that baseline moves with the catalog; the held-out set stays strict.

## 3.4.0

- **VS Code.** `--tools vscode` installs into Copilot's skill folders (`~/.copilot/skills`, or `.github/skills` with `--project`), and `install.sh mcp --tools vscode` writes the SFP server into VS Code's `mcp.json` under its `servers` key (your user file, or `.vscode/mcp.json` with `--project`), keeping other servers. VS Code is detected by its settings folder.
- **A standing instruction so the agent uses the hive.** `install.sh rules --project .` writes a short marked block to `AGENTS.md` (and `CLAUDE.md` or `GEMINI.md`); without `--project` it writes the user-level file for Claude Code, Codex or Gemini CLI. `rules --remove` takes only that block out.
- **A before and after test with real agents** (`docs/EFFECT.md`): no difference in score on five common tasks, a large one (0 of 7 to 7 of 7) on a tool the model does not know.
- **Fix: a skill about only Docker, Kubernetes or Terraform is no longer ruled out by a project's language.** FreeLLMAPI was dropped for a task that said "Python SDK". Accuracy on the evaluation sets is unchanged.

## 3.3.0

- **Plugins for more IDEs.** Every category is now also a Codex plugin (`.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`), a Cursor plugin (`.cursor-plugin/marketplace.json`), and a GitHub Copilot CLI plugin (a `plugin.json` at each plugin root, and Copilot reads the existing Claude marketplace). A root `gemini-extension.json` makes the repo a Gemini CLI extension that serves every skill through the MCP server. The installer still covers the 16 IDEs that read a skills folder. Only the Claude Code manifest is checked with its own validator; the others follow each tool's documented format and are checked by tests for shape only.
- The banner tagline names the hive.

## 3.2.0

- **Skills that need a program install it themselves.** The 93 skills that only guide a separately installed program (OmniRoute, claude-mem, Strix, FreeLLMAPI, Agent Reach, AgentShield) now carry `scripts/sfp_app.py` and that program's entry (`scripts/app.json`), and start with a note telling the agent to use them. `status` checks the requirements (Node version, Docker running), whether it is installed and whether it answers; `install` shows a plan and changes nothing; `install --yes` runs it; `start` starts it and waits for it; `update` moves to the newest release. A downloaded installer script is saved and its checksum printed before it runs, only https is accepted, and provider keys are left to the user.
- The programs and their commands are in `apps/apps.json`, with the engine in `apps/sfp_app.py`. The router skill carries all of them (`sfp_app.py list`), and `scripts/install.py apps ...` runs the same from the checkout. The ECC add-on (agents and hooks beyond the skills) is in the list.
- The catalog marks these skills with an `app` field. New tests: `tests/test_apps.py`.

## 3.1.0

- **The hive is back as the product's model.** The honeybee colony is again how SFP explains and names its choosing: five signals are scouts, agreement is quorum, overlap suppression is stop signals, roles are filled by response threshold, and history is a fading pheromone trail. The feedback loop and learning model from 3.0.0 stay, and the README maps them too: `helped` reinforces, `unhelpful` abandons, `missing` is a scout finding a new source, and the 120-day half-life is evaporation. The mapping is functional; the learner is still a regularised logistic regression.
- **Renamed again.** The skill `sfp-select` is now `sfp-hive`, the engine `mcp/sfp_select.py` is `mcp/sfp_hive.py`, `docs/SELECTION.md` is `docs/HIVE.md`, and the tests are `tests/test_hive.py` and `tests/hive_heldout.json`. The MCP tools (`select_skills`, `give_feedback`, `learning_status`, `predict_next`) are unchanged. The installer removes leftover `sfp-select` and `sfp-manager` folders that it created.
- Selection output is unchanged except for the skill's own description and the summary line of the command-line output.

## 3.0.0

- **The selector learns from feedback.** After a task, report which chosen skills `helped`, were `unhelpful`, were `ignored` or were `missing` (`give_feedback`, or `sfp_select.py feedback`). A small model of which task words go with which skills adjusts later choices, can find a skill that keyword search missed, and fades old reports. A reported mistake is fixed on the same kind of task 94% of the time. On tasks it has not seen, accuracy moved from 86.8% to 87.7%, which is within noise. `status` shows what was learned and `forget` deletes it. See `docs/SELECTION.md`.
- **Renamed.** The skill `sfp-manager` is now `sfp-select`, the engine `mcp/sfp_hive.py` is `mcp/sfp_select.py`, and the MCP tool `recommend_stack` is `select_skills`. `record_usage` is replaced by `give_feedback`, and `learning_status` is new. The installer removes a leftover `sfp-manager` folder that it created. The earlier engine stays available as `--engine v1`.
- The documentation and the README describe the algorithm in plain engineering terms. The insect-colony models it draws on are credited in `docs/SELECTION.md`. `docs/HIVE.md` became `docs/SELECTION.md`, and `docs/MANAGER.md` became `docs/PRODUCT.md`.
- The first learning design, a weight per skill, technology and signal, made unseen tasks worse and was dropped. The history is in `docs/SELECTION.md`.
- With no feedback, selection is byte-for-byte what 2.0.1 produced on all 137 evaluation tasks.
- New tests: `tests/test_learn.py` (storage and privacy, feedback validation, the model, the loop over MCP and the command line, and the learning curve) and `tests/test_select.py`.
- The README is rebuilt around selection and learning.

## 2.0.1

- **Faster, with identical answers.** Search about 5x faster, next-skill prediction about 15x, a whole decision about 3x, calls through the running MCP server 3 to 5x, and the first call after start-up about 7x. A one-shot command line call is about 25% faster. Answers were compared byte for byte on all 137 evaluation tasks before and after. See `docs/SELECTION.md#speed`.
- The sync now writes `index.json`, a saved search index that start-up loads if it matches the catalog and tokenizer exactly, and rebuilds otherwise.
- The MCP server loads the hive in the background after start-up.
- `tests/test_speed.py` pins each fast path to the plain definition it replaced, and holds speed budgets.

## 2.0.0

- **The hive.** `sfp-manager` now chooses skills with a colony algorithm modelled on how honeybees divide work (`mcp/sfp_hive.py`): independent scouts and a quorum rule, stop signals between rival skills, response thresholds that decide how many skills each job takes, thresholds that learn from recorded outcomes, and pheromone trails that evaporate with a 30-day half-life. On 22 new tasks written before it existed, it put the right skill in the stack 86% of the time, against 68% for v1 and 14% for plain search. See `docs/HIVE.md`.
- `recommend_stack` and `predict_next` in the MCP server use the hive. `--engine v1` keeps the previous engine available.
- The `sfp-manager` skill tells the agent to ask once per phase of work, and lists the colony rules in plain words for when Python is not available.
- New held-out task set `tests/hive_fresh.json` and tests `tests/test_hive.py`.
- Fixed: v1 could recommend `sfp-manager` itself.
- The README is rebuilt around the hive, with figures regenerated from the evaluation on every sync.

## 1.x

- `sfp-manager` and the v1 stack engine, the MCP server, the installer for 16 IDEs, the ECC and OmniRoute integration guide, search ranking and the generated README.
