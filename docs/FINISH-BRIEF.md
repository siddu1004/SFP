# Finishing the extension: connect, check, polish

Everything the interface shows now comes from the engine on `main` (version 3.14): areas, bundles pushed whole, needs, live attaching, the model router and `sfp_hive.py doctor`. The sidebar library and its detail window were rebuilt on `feat/chat-extension` (commit `efba8e4`). This brief is what is left. Do it in the order below, push after each numbered part, and report the checks at the end as pass or fail with one line of evidence each.

## 0. Start clean
- `git fetch`, `git merge origin/main`. Do **not** commit files that `scripts/sync.py` generates (`catalog.json`, `index.json`, `SKILLS.md`, `plugins/`, `.claude-plugin/`, `.agents/plugins/`, `.cursor-plugin/`, `gemini-extension.json`, `README.md` counts, `sources.lock.json`): after a sync, restore them from `origin/main`. Your sync pulls newer upstream skills and breaks `test_saved_index_matches_a_fresh_build`.
- `python -m unittest discover -s tests` and `npm test` must both pass before you start.

## 1. Pushed bundles (`docs/BUNDLES.md`, "Brief for Antigravity")
`select`, the live result and `@hive` now carry `bundles` and `bundle`. Show the banner, the numbered skills in order, "Not this bundle" and "Attach whole bundle" as described there. Add the types you need to `src/hive.ts` (`BundleMatch` exists).

## 2. Doctor: one place that says whether everything is connected
- Add the command `sfpHive.doctor` and a **Check connection** button in the Insights tab and at the top of the Models view. It runs `hive.doctorArgs` and shows the result as a list: a green, amber or red mark, the check's name, its one-line detail and, when it is not ok, the `fix` with a **Copy** button. A failed run still prints JSON; use `hive.parseDoctor` on stdout whatever the exit code.
- Run it quietly once when the extension activates, and again when `sfpHive.sfpPath` changes. If the result is `fail`, show a warning on the status-bar item with the first failing check; if `warn`, nothing but the list.
- If the checkout cannot be found, the list is one red line with a button to the setting `sfpHive.sfpPath`.

## 3. Connectivity checks, with real calls
Write these as `test/e2e/drive.js` steps against a real VS Code (code-server) and report them:
- **C1** Open the Skill Library: 11 areas, 819 skills.
- **C2** Type in Choose: skills appear as chips within one second of stopping; a task about a signup form shows the "Bundle: Accessible form" banner with its four skills in order.
- **C3** "Not this bundle" removes those skills and they do not come back while typing.
- **C4** Send the message: exactly one line is added to `decisions.jsonl`.
- **C5** A task that needs a 3D model shows the need card with its action (set `MESHY_API_KEY`).
- **C6** Models view: with no local server it says so and shows the setup step; with a fake local server on 11434 (a few lines of Node that answers `/api/tags` and `/v1/chat/completions`) it lists the model, Set up writes `routes.json`, Start shows the URL, and Try it answers through the fake.
- **C7** Stop the fake, send Try it again: the status shows the model cooling down and a message that says why.
- **C8** Check connection shows no red line.

## 4. UI touch-ups (apply to every view, check each in dark, light and high contrast at a sidebar width of 260 px)
- Keep the Library's style: flat, one accent, theme variables only, no coloured cards. Make the **SFP Hive** and **Models** views match it (no filled blue badges, no heavy boxes, quiet counts).
- Every view has a loading state, an empty state with one sentence of help and an error state that names the fix. No view is ever blank.
- First run: when `decisions.jsonl` is empty, show a three-line welcome in Choose: "Describe a task, see the skills, send it." with a button that fills an example. Remove it after the first decision.
- Language: short, plain sentences in the user's words. No jargon (say "Models", not "router policy"; "Not this bundle", not "exclude"). Check every label, tooltip and error.
- Focus rings visible on every control, tab order sensible, Escape closes menus and clears search, nothing needs a mouse.
- Remove console logging, dead code and unused CSS; every dynamic string escaped; no inline styles or scripts.
- The status bar shows `Hive` and, when a bundle is attached, its name; clicking opens Choose.
- `README.md` of the extension: what it is in two sentences, three screenshots (Areas, a bundle opened, the skill detail), the settings table (`sfpHive.*`), and "if something does not work, run **Check connection**".
- Package the `.vsix` and report its size.

## 5. Report
List C1 to C8 and the earlier checks that were never reported (L1 to L12 in `docs/LIBRARY-BRIEF.md`, A1 to A6 in `docs/LIVE.md`, R1 to R6 in `docs/ROUTER.md`) as pass, fail or not done, one line of evidence each. Say what you could not test and why. Do not describe work as done that you did not run.
