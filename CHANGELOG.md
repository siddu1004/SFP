# Changelog

## 3.17.7

- **README.** New hero tile of three numbers under the banner, a "Does It Make the Agent Better?" section with charts of the design test and of held-out accuracy (light and dark), a tip on how the feedback loop learns (94% of reported mistakes fixed on the same task, +0.7 points on new ones), and an honest note on where skills do not help yet. `bench/charts.py` draws the charts from the saved results.

## 3.17.6

- **A page is design work, whatever it is about.** "Design a pricing page for a webhook tool" chose `price-framing` and `omni-webhooks` and no design skill: the task's subject outweighed what was being built. When a task asks to design or build a UI artifact (a page, screen, dashboard, form, empty state, or HTML/CSS), the hive now also searches for UI design skills and gives the design phase a job in the stack. Those skills join as candidates below a precise match, so "brutalist website design" still gets the brutalist styles. Benchmark 89.0%, projects 79.2%, held-out 86.4%: unchanged.
- **Design benchmark.** `bench/design/run.py` measures design work over rounds: a reviewer model scores screenshots of the page, and its requested changes go back to the agent until it would ship the page. Three arms: no skills, SFP's choice, and two design skills picked by hand.

## 3.17.5

Three wrong choices found by the agent benchmark (docs/AGENT-BENCH.md), fixed by rules that hold beyond those tasks.

- **Building a rate limiter is not running out of tokens.** "Add rate limiting to the payments API" got the LLM-quota skills, because "rate limit" and "429" triggered `never-run-out`. A capability can now list `unless` patterns (add, implement or enforce rate limiting; per client or endpoint; Retry-After) that cancel it unless the task also speaks of models, tokens or providers. A bundle made only of one capability's skills (`keep-going`) now fits only when that capability fires.
- **Bundles respect the project.** "Write tests for cart.py" in a Python project got the Go service bundle: bundles were matched on words alone. A bundle whose skills belong to technologies the project and task do not use is no longer attached, as a single skill would not be.
- **Platform skills need their platform.** n8n is now a technology, and a skill for a platform (n8n, X/Twitter, LinkedIn and others) needs that platform in the task or project even when its language matches: the bug fix in a Python project no longer gets `n8n-code-python`.
- **The request comes first.** In a longer task the first clause ("Add rate limiting to the payments API") is also searched on its own, so the details after it cannot drown it.
- **public-apis joins when asked for.** Its description lists 51 kinds of API, so words matched it for any task that said "API"; it is now a candidate only when the find-an-API capability fires.

Scores: benchmark 87.9% to 89.0%, projects 79.2% (unchanged), held-out 86.4% (unchanged).

## 3.17.4

- **A platform skill needs its platform named.** "Add rate limiting to the payments API" chose `x-api` (an X/Twitter skill whose description mentions X's own rate limits). X/Twitter and the other social platforms are now technologies, so a skill for one platform counts against a task that never names it; a description that lists many platforms stays general. The "named by the task" rule, which lets a skill past the project's veto, now also needs the task to use one of the skill's distinctive words: its technology, or a word of its name that at most 5% of skills share ("api" is in 65). Benchmark, project and held-out scores are unchanged (87.9%, 79.2%, 86.4%).
- **A task you chose stays chosen.** The agent's skills file went to whichever came last, so a routine activity refresh replaced a task you had just typed within seconds. Now the task holds until you choose another, or until the hive sees the work move to a new phase at least five minutes later.
- **Insights layout.** The health list no longer wraps one letter per line in a wide sidebar.

## 3.17.3

- **Installation guide.** New [docs/INSTALL.md](docs/INSTALL.md): SFP, the skills, the SFP Hive extension, automatic skills, local models and the router, and Git-to-skill, each step with a check, plus troubleshooting and removal.
- **Cross-platform npm package & npx launcher.** `sfp-hive` on npm: run `npx sfp-hive install` to bootstrap and install SFP skills into all detected IDEs across Windows, macOS, and Linux without bash. Supports zero-config MCP server via `npx -y sfp-hive mcp`.
- **README.** The extension section now describes what it does today (automatic skills, Now, Choose, Library, Models, Insights with skill history) and no longer says it has not been run in Antigravity: it has.

## 3.17.2

- **Sharper automatic skills from activity.** When the agent's skills come from the phase the hive follows (not a task you typed), it now gets the phase's best bundle, in order, plus at most two other skills the hive is sure of (score 0.9 or more). Activity is weak evidence, and file names in a skills repository had brought in unrelated skills (an n8n skill and a web3 hashing skill while debugging). A task you type keeps the full choice.

## 3.17.1

- **Skill history.** Each time the agent is given skills, the extension records which ones, for which prompt or phase, and when, in `skill_history.jsonl` in your data folder (local only). The Insights tab lists the latest 15.
- Removed Antigravity's `hive-chat.md` rule and its section in `AGENTS.md`, which made the agent re-run the hive and print a banner on every reply; automatic skills replace it.
- The extension tests no longer write the automatic skills rule into the checkout, and `.gitignore` keeps it out.

## 3.17.0

- **The agent gets its skills automatically.** The extension writes the skills the hive chose, in order and with the path of each `SKILL.md`, plus the rest of any loaded bundle, to `.agents/rules/sfp-active-skills.md` in the workspace, and rewrites it whenever the choice changes: a task you chose or the phase the hive follows. The agent reads that rule on every turn. The sidebar says "The agent has N skills automatically" with a switch; Copy prompt and pins still work by hand. Settings `sfpHive.autoSkills` and `sfpHive.autoSkillsFile`, command "Turn automatic skills on or off".
- Skills a bundle or a need brought in now say so ("part of the \"Accessible form\" bundle", "needed to make 3D models...") instead of "pinned by you".
- The Insights connection list shows a fix only for checks that need one.

## 3.16.1

- **Fixed: "search index stale" on Windows.** The index fingerprint was a hash of the raw bytes of `catalog.json`, and Git on Windows can check it out with CRLF line endings, so a correct index looked stale (and `doctor` warned). The fingerprint now ignores line endings, and `.gitattributes` keeps JSON files LF.

## 3.16.0

- **The router follows your local models.** While it serves, `sfp_route.py` looks for local runtimes again every 30 seconds (`--rediscover N`): one that starts joins with its models, new models are added, and one that stops answering is switched off until it returns.

## 3.15.0

- **Loaded bundles for the current phase.** `sfp_hive.py track` now returns `bundles`: the bundles that hold the skills chosen for the phase of work, best first, each with the skills it covers and the rest that load with it (`sfp_library.phase_bundles`). The Now tab shows them under "Loaded bundles", with the numbered skills and an "Attach whole bundle" button. The Now tab's wording is plain ("Confidence 62%", "Based on recent workspace activity"), and it refreshes by itself every `sfpHive.autoRefreshSeconds` seconds (default 5, 0 for manual).

## 3.14.0

- **`sfp_hive.py doctor`** checks that everything is connected: catalog and search index, data folder, selection, live attaching, needs, the skill library, local models, the router and the MCP server, each as ok, warn or fail with the command that fixes it. `--json` for the editor.

## 3.13.0

- **The hive pushes whole bundles.** A task that fits a bundle gets all of its skills, in the bundle's order, instead of a few loose ones. Matching uses the task's words against each bundle and how many of its skills the hive already chose; a good fit is attached whole (even past the usual four skills), a weaker one is suggested and its remaining skills preloaded. `select --bundles push|suggest|off`; `select`, `live` and `select_skills` return `bundles` and `bundle`. Measured: right bundle first for 88% of 24 dev tasks and 50% of 10 held-out ones, with no wrong bundle pushed. `docs/BUNDLES.md`.

## 3.12.0

- **Areas.** `families.json` groups the 40 clusters and 36 bundles into eleven areas (Design and UI, Build apps and services, Test and quality, Security, Ship and run, Prompts and agents, Models and gateways, Run a project, Research and docs, 3D and creative, Business and automation). The `library` payload carries `families`, and every skill, cluster and bundle names its area. Two new bundles: Never run out of tokens, Find the right API.
- `sfp_hive.py skill NAME` gives everything the skill detail window shows: the full description, when to use it, its area, topic and goals, the bundles it is in and similar skills.
- Recipe bundle names keep their acronyms ("Critique a UI").

## 3.11.0

- **A router for your models.** `mcp/sfp_route.py` finds the models running on your machine (Ollama, LM Studio, llama.cpp, Jan, vLLM), adds free and paid providers whose key is set, and serves one OpenAI-compatible endpoint. Each request is sized; local models go first, the weakest one that is strong enough; when a model is rate limited, out of credit, down or too small, it cools down and the next one answers. No dependencies, no keys stored. `docs/ROUTER.md`.
- **The project cannot veto what the task names.** A skill the task's words name best is no longer dropped as being for another technology than the project (a 3D skill in a web project). Project-based selection: 75.0% to 79.2% hit, first-place 58.3% to 62.5%; the other sets are unchanged.
- **The project fingerprint ignores copies of other projects** (`plugins/`, `fixtures/`, `examples/`, `third_party/`, `site-packages/`): this repository no longer looks like a FastAPI project because of a vendored skill's requirements.
- The `never-run-out` need checks the router first and gives the one command to set it up or start it.

## 3.10.0

- **Needs.** The hive now knows what a model cannot do alone. `capabilities.json` lists eight abilities (3D from images, reading websites, never running out of tokens, finding a free API, generating media, checking work in a browser, remembering, pentesting) with the skills, programs and keys behind each. A task that needs one gets the provider skill attached, the follow-on skills preloaded, and with `--check` the exact install, start or key step that is missing (OmniRoute, FreeLLMAPI and Agent Reach through `apps/sfp_app.py`). `sfp_hive.py needs`, and `needs` and `preload` in `select`, `live` and `select_skills`. Detection costs about 0.1 ms, so it also runs while typing. `docs/NEEDS.md`.

## 3.9.0

- **Skills follow what you type.** `sfp_hive.py live` takes a half-typed message and returns the skills to attach: it waits for enough words, keeps the list steady while you keep typing the same idea, moves only the skill that no longer fits when the topic shifts, honours your pins and removals, and logs nothing until the message is sent. `src/live.ts` debounces and drops stale answers. `docs/LIVE.md` has the rules and the brief for wiring it to the chat input.

## 3.8.0

- **The skill library.** Every skill now has a purpose, what it is trying to do, in 15 purposes (Design interfaces, Build features, Test and verify, Deploy and release and more), assigned by `purposes.json`: a name pattern, else the skill's cluster, else its strongest job when its name says so. Measured against one person's labels: 83% on the 120 skills the rules were tuned on and 78% on 40 held-out ones (`docs/LIBRARY.md`).
- **Bundles.** `bundles.json` has 34 named, ordered sets of skills for one job: the 18 hive recipes by reference, and 16 new ones such as "Prepare a release", "Add tests to legacy code" and "Accessible form". `bundle-add` and `bundle-remove` keep your own. `select --bundle ID` pins a bundle's skills into the choice for a task, and feedback learns from it.
- **One payload for the editor.** `sfp_hive.py library` prints everything the sidebar needs in about 0.2 s. `src/library.ts` in the extension searches it without calling Python: whole words in names first, word starts, related words, purposes and clusters, descriptions, and one typo; about 5 ms per search over 819 skills. Its tokenizer is checked against the Python one.
- `docs/LIBRARY-BRIEF.md` is the prompt for building the sidebar, starting with fixes for what a review of Stage 2 found (two registrations of one view, an empty renderer, a loose CSP, nothing escaped).

## 3.7.0

- **Follow the agent.** `sfp_hive.py track` reads workspace events (saves, commands and their exit codes, errors, prompts), turns them into evidence for the eleven phases of work, smooths it with one Kalman filter per phase, and predicts the next phase with a Markov chain over phase changes, learned from your sessions on top of a prior for the usual order of work. The phase is passed to the hive as a hint, and also brings the phase's own words into the search, so the skills change when the work does. On hand-labelled sessions the filter is steadier than following the last event, and on the held-out set about 7 points less accurate; `docs/TRACKING.md` has the numbers.
- **Clusters.** `clusters.json` groups all 819 skills into 40 named clusters (UI components, animation, testing, GSD workflow, Blender scenes and more); `sfp_hive.py clusters` lists them with usage, and `cluster-add` and `cluster-remove` manage clusters of your own.
- The extension's bridge has the calls for tracking, an activity buffer and clusters, with tests (25). `docs/HIVE-STUDIO.md` is the prompt for Antigravity to merge the two SFP extensions into one, with the Now, Choose, Library and Insights tabs.

## 3.6.0

- **See and steer the choice.** `select --explain` lists the top candidates with their five signal votes, the signals that backed each, its learned preference, token cost, and the exact reason it was chosen or dropped (no agreement, overlap with a chosen skill, token budget, stack full, another technology). `--exclude` rules skills out and `--include` pins them in; pinned skills say so. With no options the choice is unchanged. The extension's `src/hive.ts` exposes them, and turns an intervention into feedback (removed is `unhelpful`, added is `missing`).
- `docs/HIVE-INSPECTOR.md`: the prompt for Antigravity's agent to build a visible button and inspector on top of this, the checks to run, and how to evaluate the choosing process.
- The extension's install and verify scripts also look for `antigravity-ide`, the command's name on Windows (found by Antigravity's own agent while checking the extension).
- Recorded in `docs/HIVE.md`: the project's technologies are counted twice, so a skill named after the stack can pass for one the task asked for (`react-three-fiber` for a signup form in React). The fix tried cut the held-out hit rate from 86% to 64% and was reverted.

## 3.5.0

- **The hive as an extension for Antigravity and other VS Code editors** (`extensions/antigravity-hive/`, TypeScript, MIT). A status-bar item and an activity-bar view choose the skills for a task, group them as base, check and finish, copy a ready prompt for the agent panel, open each skill, and record `helped`, `unhelpful`, `ignored` and `missing` feedback. Commands open the installer for skills, the standing instruction and programs such as OmniRoute, showing the plan first. `install.py` in that folder builds the `.vsix` and installs it with the editor's own command. 18 tests, including a real end-to-end run of the hive. It was run in a real VS Code 1.117 (code-server) with a browser-driven test, which found and fixed one bug; it has not been run inside Antigravity itself. `docs/ANTIGRAVITY.md` explains the design, why it is an extension and not a patch to the editor, and has seven implementation prompts for extending it.
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
