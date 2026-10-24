# SFP Hive: one extension that follows the agent

Two SFP extensions are installed in Antigravity today: the "SFP Hive Monitor" webview on `feat/chat-extension` (folder `extension/`) and the tested TypeScript one on `main` (folder `extensions/antigravity-hive/`). This brief merges them into one, with a professional design, and adds what the engine can now do:

- **Follow the agent.** Phase tracking from workspace activity, with a Kalman filter and a Markov chain: `docs/TRACKING.md`.
- **See and steer the choice.** `--explain`, `--include` and `--exclude`: `docs/HIVE-INSPECTOR.md`.
- **Browse 819 skills as about 40 clusters,** and add your own.

The engine and the bridge are built and tested. `extensions/antigravity-hive/src/hive.ts` has every call the interface needs: `selectArgs`, `feedbackArgs`, `interventionFeedback`, `trackArgs`, `parseTrack`, `ActivityBuffer`, `relative`, `clustersArgs`, `clusterAddArgs`, `clusterRemoveArgs` and `parseClusters`. The build is the interface and the wiring.

## The prompt

Paste this into Antigravity's agent with the SFP checkout open. It stops after each stage for you to check.

> Build "SFP Hive", one extension that replaces the two SFP extensions. Read `docs/HIVE-STUDIO.md`, `docs/TRACKING.md`, `docs/HIVE-INSPECTOR.md`, `docs/ANTIGRAVITY.md`, `extensions/antigravity-hive/src/hive.ts`, `extensions/antigravity-hive/src/extension.ts`, and the `extension/` folder on `feat/chat-extension` first.
>
> Rules for the whole job:
> - Work on the `feat/chat-extension` branch, and start by merging `origin/main` into it.
> - Do not read, copy or modify Antigravity's own installed files. Use only the public VS Code extension API.
> - Add no runtime dependencies. Every call to the hive goes through `src/hive.ts`. Never send anything off the machine.
> - Keep `npm test` in `extensions/antigravity-hive` and `python3 -m unittest discover -s tests` passing, and add tests for everything you add.
> - Commit after each stage with a clear message and push, so the work can be reviewed. Stop after each stage with a short report and what I should look at.
>
> **Stage 1, one extension.** Keep `extensions/antigravity-hive` (TypeScript, tested) as the only extension. Keep its id `siddu1004.sfp-hive`, set the display name to "SFP Hive" and the version to 0.2.0. Port into it the useful parts of `extension/`: the webview design, the `@hive` chat participant (register it only if `vscode.chat.createChatParticipant` exists), and the Train command (`python3 mcp/sfp_hive.py train`). Then delete the `extension/` folder and its test, and tell me to uninstall the old "SFP Hive: Dynamic Skill Monitor" extension.
>
> **Stage 2, layout and design.** One webview view, "SFP Hive", in the activity-bar container, with four tabs: **Now**, **Choose**, **Library** and **Insights**. Also add a status-bar item on the right, under the agent window, showing the current phase and the number of skills (for example "Test · 3"); clicking it opens Now. The design must look professional:
> - Use the editor's codicons only, no emoji. Take every colour from the theme variables (`var(--vscode-...)`), with one accent colour, and check it in a light and a dark theme.
> - Use the editor's font and an 8-pixel spacing grid, with type sizes 11, 13 and 16.
> - Each section has a loading state, an empty state with one sentence of help, and an error state that says what to do.
> - It works at a sidebar width of 260 pixels.
> - Every control can be reached with the keyboard, has a visible focus ring and an accessible label.
> - Motion is off when the user asks for reduced motion.
> - Webview rules: a content security policy with a nonce, no remote resources, and all text escaped.
>
> **Stage 3, Now: follow the agent.** Feed workspace activity into an `ActivityBuffer`:
> - `workspace.onDidSaveTextDocument` sends `save`, and `onDidCreateFiles` and `onDidDeleteFiles` send `create` and `delete`. Paths go through `relative()`, so only paths inside the workspace are sent.
> - `window.onDidStartTerminalShellExecution` and `onDidEndTerminalShellExecution` send `run` with the command line, cut to 200 characters, and the exit code. This only works when shell integration is available; skip it quietly when it is not.
> - `languages.onDidChangeDiagnostics` sends `diagnostics` with the workspace error count, debounced to once every 10 seconds.
> - `window.onDidChangeActiveTextEditor` sends `open`.
> - A task typed in Choose, or sent to `@hive`, is a `prompt` event. Do not try to read the agent window's contents: there is no API for it, and it would be private.
>
> Flush the buffer to `trackArgs` every 20 seconds when it has events, and at once after a `run` that ends with an exit code. The Now tab shows:
> - the phase, its layer and a confidence bar (from the Kalman filter);
> - a thin stacked bar of the phase shares, coloured by layer;
> - "Next likely" chips with the Markov probabilities;
> - the skills for this phase as cards, each with its reasons and Open, Helped, Unhelpful and Remove;
> - "Coming up", the skills for the likely next phase;
> - the last five phase changes;
> - a "Follow the agent" switch;
> - "Copy for the agent", which uses `buildPrompt`.
>
> When the phase changes with a confidence of at least 0.6, update the status bar and show at most one quiet notification every 2 minutes, offering "Use these skills". Add the settings `sfpHive.follow` and `sfpHive.followCommands`, both on by default.
>
> **Stage 4, Choose.** The Inspector from `docs/HIVE-INSPECTOR.md` stage 3, as this tab: the task box, the chosen cards, "Considered but not taken" with signal bars, include and exclude, Re-choose with the difference shown, Apply, and the feedback from `interventionFeedback`.
>
> **Stage 5, Library: clusters.** Show a grid of clusters from `clustersArgs`. Each card shows the name, the number of skills, how many have been used, and the description. Add one search box over clusters and skills. Opening a cluster lists its skills with descriptions and usage, and each skill has Open, "Pin to the current task" and "Add to a cluster of mine". Add "New cluster" (a name, then pick skills) and "Remove" for clusters of your own, using `clusterAddArgs` and `clusterRemoveArgs`. Mark your clusters.
>
> **Stage 6, Insights.** Show:
> - the most chosen skills;
> - helped against unhelpful per skill;
> - the session's intervention rate and the share of chosen skills kept (from the Inspector counters);
> - the learning status from `sfp_hive.py status --json`;
> - the Train button;
> - one line on how accurate phase tracking is, linking to `docs/TRACKING.md`.
>
> **Stage 7, tests.** Write unit tests for the new pure functions, such as the notification throttle and the view models for the phase bar and the chips. In `test/extension.test.js`, check against the stand-in `vscode` that each workspace event reaches the buffer in the right shape. Extend `test/e2e/drive.js` (code-server) to open each tab, run a task, see the phase card change after a `go test` command in the terminal, open a cluster and add a cluster of your own.
>
> **Stage 8, check it here.** Run `python3 extensions/antigravity-hive/install.py`, ask me to reload, and walk me through checks S1 to S12 below one at a time. Then write the report as a table.

## Checks

| ID | Do | Expected |
|---|---|---|
| S1 | Look at the activity bar and the status bar after a reload | One SFP Hive icon, and the old monitor gone; a status item on the right |
| S2 | Open the SFP Hive view | Four tabs: Now, Choose, Library, Insights |
| S3 | Ask the agent to add tests to a file and run them | Within about 20 seconds Now shows Test, with a confidence bar and test skills |
| S4 | Make a test fail, then edit the source | Now moves to Debug; "Next likely" shows Test |
| S5 | Wait for a phase change | One quiet notification, and the status bar shows the new phase |
| S6 | Click Helped and Remove on a skill in Now | Feedback is recorded (check `~/.sfp/feedback.jsonl`) and the skill is replaced |
| S7 | In Choose, run a task with Explain | Chosen cards, and "Considered but not taken" with reasons and signal bars |
| S8 | Library: search "animation" | The Animation and motion cluster and its skills |
| S9 | Create a cluster of your own from three skills, then remove it | It appears, marked as yours, then disappears |
| S10 | Insights | Most-used skills, the learning status, and the Train button works |
| S11 | Switch to a light theme, narrow the sidebar, use only the keyboard | Everything stays readable and reachable |
| S12 | Turn off "Follow the agent" | No more tracking calls (check that `track_state.json` stops changing) |

## Who reviews the work

Each stage is pushed to `feat/chat-extension`. The commits are watched and reviewed from the SFP side, and problems are reported back with the file and line.
