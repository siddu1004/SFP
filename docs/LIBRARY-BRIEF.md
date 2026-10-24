# Brief: the Skill Library in the sidebar

You are building the interface for the skill library in the SFP Hive extension (`extensions/antigravity-hive/`). The engine, the data and the search are done and tested on `main`. Your job is the interface and the wiring, and fixing what Stage 2 left unfinished. Read `docs/LIBRARY.md` first, then `src/library.ts`, `src/hive.ts` and `src/extension.ts`.

## Paste this into Antigravity's agent

> Work on the `feat/chat-extension` branch. First merge `origin/main` into it, then run `python scripts/sync.py` and check that `catalog.json` has no backslash in any `path`. Then carry out `docs/LIBRARY-BRIEF.md` stage by stage. After each stage: run `python -m unittest discover -s tests` (all must pass) and `npm test` in `extensions/antigravity-hive` (all must pass), commit with a clear message, push, and stop with a short report of what changed and what I should look at. Do not start the next stage until I say so. Rules: use only the public VS Code extension API; do not read, copy or change Antigravity's own files; add no runtime dependencies; every call to the hive goes through `src/hive.ts`; all search and grouping goes through `src/library.ts`, which you must not reimplement; every piece of text you put in a webview is escaped; add tests for everything you add.

## What is already built, and the contract

`python3 mcp/sfp_hive.py library` prints one JSON object. In `src/hive.ts`: `libraryArgs(root)`, `parseLibrary(json)` (returns a `Library`), `bundleAddArgs`, `bundleRemoveArgs`, and `selectArgs(root, task, project, max, {bundle, include, exclude, explain})`. In `src/library.ts`: `searchLibrary(lib, query, {purpose, cluster, limit})` returns `Hit[]` (`name`, `score`, `marks` to highlight in the name), `groupBy(lib, 'purpose' | 'cluster' | 'bundle', hits?)`, `searchBundles`, `summary`, and the types `Library`, `LibrarySkill`, `Purpose`, `LibraryCluster`, `Bundle`, `Group`, `Hit`. The search runs in the extension host or in the webview from the same payload; run it in the extension host and send results to the webview, so the webview stays simple.

Payload shape (fields the interface uses):

- `purposes[]`: `id`, `name`, `description`, `icon` (a codicon name, without the `codicon-` prefix), `count`, `used`.
- `clusters[]`: `id`, `name`, `description`, `mine`, `count`, `used`, `skills[]`.
- `bundles[]`: `id`, `name`, `goal`, `purpose`, `when`, `skills[]` (in order), `mine`, `recipe`, `tokens`.
- `skills{ name: { d, category, cluster, purpose, also[], usage?, app? } }`. `d` is a one-line description. `usage` has the counts `chosen`, `helped`, `unhelpful`, `ignored`, `missing`. `app` names a program the skill needs installed.

## Stage 1: fix what Stage 2 left

These come from a review of commit `557eedd`. Fix each, with a test.

1. `src/extension.ts` registers `sfpHive.stack` twice, as a tree (`StackView`) and as a webview. Remove the tree, its menus (`view/item/context`, the tree-only `view/title` entries) and its tests, and move the unit tests in `test/extension.test.js` and `test/e2e/drive.js` to the webview (message handlers and rendered output).
2. `media/studio.js` `renderState` is empty, so no tab shows data. Make Now and Choose render the real state: the task, the chosen skills as cards (name, phase, layer, reasons, tokens) with Open, Helped, Unhelpful and Remove, and the decision id. The `refresh` message from the Now tab has no handler in the extension: handle it.
3. CSP: remove `https:` from `img-src` (no remote resources). Remove the inline `style=` attributes and `'unsafe-inline'` from `style-src`: use classes in `studio.css`.
4. Add one `escapeHtml` helper and use it for every dynamic string put in HTML. Add a test that a skill name or reason containing `<img src=x onerror=alert(1)>` renders as text.
5. Replace the hand-drawn SVG icons with codicons (`@vscode/codicons` is not allowed as a runtime dependency, so reference the editor's own codicon font through the webview's `asWebviewUri` of the `codicon.css` that ships with the editor, or use the `$(name)` syntax only in native UI; if the font cannot be loaded in a webview, say so in your report and keep small inline SVGs in one file).
6. Keyboard: tabs use `role="tablist"`, `role="tab"`, `aria-selected`, roving `tabindex`, and respond to Left, Right, Home and End. The task input submits on Enter.
7. Every tab has a loading state, an empty state with one sentence of help, and an error state that says what to do. Replace the fixed "819 skills across 24 categories" with the real counts from the payload.
8. The accent colour must not be `--vscode-focusBorder` (that is the focus ring). Use `--vscode-button-background` or the editor's link colour for the accent, and remove the hard-coded colours.

## Stage 2: the Skill Library view, in the left sidebar

Add a webview view `sfpHive.library`, named "Skill Library", in the SFP Hive activity-bar container, below the existing view. Remove the Library tab from the studio view; leave three tabs. Everything the old Library tab was meant to do moves here.

Layout, top to bottom, working at a sidebar width of 260 pixels:

1. **Search box**, sticky at the top, with a clear button and a result count ("12 of 819"). Search runs as you type (debounced 80 ms) through `searchLibrary`. Escape clears it. The first match is focused with the Down key.
2. **Grouping switch**: three segmented buttons, "What it does", "Clusters", "Bundles". Remember the choice in `workspaceState`.
3. **Groups**, collapsible, each with an icon (purposes), the name, and a count (`12` or `3 of 40` while searching). Purposes use the codicon from the payload. When there is a query, groups with no matches are hidden and the rest are expanded.
4. **Skill rows**: the name with the matched parts highlighted from `Hit.marks` (as `<mark>`), the one-line description cut to one line with the full text on hover, small tags for the purpose and the cluster, and a usage mark when the skill has been chosen before (for example "chosen 4, helped 3"). A skill that needs a program (`app`) shows a small "needs a program" tag. Actions on hover or focus: **Open** (the skill's `SKILL.md`), **Pin to task** (adds it to the current task's pinned list, which Choose reads), **Add to bundle** (a quick pick of your own bundles, plus "New bundle...").
5. **Bundle cards** (in Bundles mode): the name, the goal, "when", the skills as an ordered list of chips, the token estimate, and a "yours" tag for your own bundles. Actions: **Apply**, which pins all the bundle's skills for the current task by calling `selectArgs(..., {bundle: id})` and showing the result in the Choose tab; **Copy prompt**, which copies `buildPrompt` for the bundle's selection; for your own bundles, **Edit** and **Delete**. A **New bundle** button at the top of the Bundles group: a name, a purpose (quick pick from the payload's purposes), a goal, and the skills (multi-select quick pick over the library, searchable). Calls `bundleAddArgs`.
6. **Footer**: counts from `summary()`, and a refresh button.

Behaviour:

- Load the payload once at activation and on refresh. Reload it when `catalog.json` or your data folder's `bundles.json`, `clusters.json` or `feedback.jsonl` change (a `FileSystemWatcher` on the checkout and the data folder, debounced to 1 second).
- A search never calls Python.
- Applying a bundle is a normal decision: it is logged, and thumbs on its skills teach the hive.
- If the checkout cannot be found, or Python fails, show the error state with a button to the setting `sfpHive.sfpPath`.

Also add three commands: `sfpHive.searchSkills` (a quick pick over the same search, for keyboard users; picking a skill opens its file), `sfpHive.applyBundle` (a quick pick of bundles), and `sfpHive.focusLibrary`. Add them to the manifest, and update the test in `tests/test_extension.py` that compares declared and registered commands.

## Stage 3: wire Now and Choose to it

- **Choose** shows "Pinned" skills above the task box (from Pin to task and Apply), each removable, and sends them as `include` with the task. A bundle you applied shows its name.
- **Now** is the follow-the-agent tab from `docs/HIVE-STUDIO.md` (stage 3 there). Do it after the library is accepted, not before.

## Tests (every stage)

- Message-handler tests in `test/extension.test.js` against the stand-in `vscode`: for each message the webview sends, that the extension calls the hive with the right arguments and replies with the right state.
- A rendering test per view: the HTML for a small fixed payload, with escaping.
- `test/e2e/drive.js` (real VS Code through code-server, see `test/e2e/README.md`): open the Skill Library, type "anim", see `animate` listed with a highlight, switch to Bundles, apply `ship-a-page`, see the four skills pinned in Choose, and check the decision in `feedback.jsonl`'s sibling `decisions.jsonl`.

## Acceptance checks

I'll run these with you after each stage. Report each as pass or fail with one line of evidence.

| ID | Check | Expected |
|---|---|---|
| L1 | Open the SFP Hive container in the left sidebar | Two views: SFP Hive and Skill Library |
| L2 | Look at the Skill Library with no search | 15 groups by "What it does", counts add up to 819 |
| L3 | Type `anim` | Results within 100 ms, `animate` listed, the matching letters highlighted, count shown |
| L4 | Type `dockr` | `docker-patterns` first |
| L5 | Switch to Clusters, then Bundles | Clusters and bundles listed, search still applies |
| L6 | Open the bundle "Prepare a release" | Five skills in order, a token estimate |
| L7 | Apply it | Choose shows five pinned skills, "pinned by you", and the bundle name |
| L8 | Make a bundle of your own from three skills, then delete it | It appears marked as yours, then disappears; `bundles.json` in the data folder changes |
| L9 | Click Open on a skill | Its `SKILL.md` opens |
| L10 | Use the keyboard only: focus the search, type, arrow down, Enter | A skill opens; every button has a visible focus ring |
| L11 | Switch to a light theme and narrow the sidebar to 260 px | Readable, no horizontal scrolling, nothing cut off |
| L12 | Rename the checkout so it cannot be found | An error state with a button to the setting, not a blank view |
