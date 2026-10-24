# The hive in Antigravity

`extensions/antigravity-hive/` is a VS Code extension that puts the hive inside the editor: type a task, get the few skills it needs in order, copy a ready prompt for the agent panel, and tell the hive which skills helped. It works in Antigravity and in VS Code, Cursor, Windsurf and other forks of VS Code.

## What Antigravity is written in

Antigravity is a fork of VS Code, so it is an Electron app written in TypeScript. Extensions use the same API as VS Code extensions: TypeScript or JavaScript, a `package.json` manifest and the `vscode` module. By default it installs from the Open VSX registry rather than Microsoft's marketplace, and it installs a `.vsix` file like any other fork. See [Antigravity VS Code setup](https://jimmysong.io/blog/antigravity-vscode-style-ide/) and [the Open VSX note on forks](https://www.bleepingcomputer.com/news/security/vscode-ide-forks-expose-users-to-recommended-extension-attacks/).

The extension is therefore written in **TypeScript**, plus the hive itself, which stays in Python and is called as a program.

## Why this is an extension and not a patch

You asked for nothing that crosses a licence line. The editor core of a VS Code fork is open source, but the product built on it has parts that are not, and its terms are Google's. Changing its installed files is not needed and not safe: an update would overwrite the change, and it could break the terms of use. An extension is the supported way in, uses only the public extension API, and every line of it is MIT code in this repository. Nothing was copied from Antigravity.

## Install

You need Node.js 18 or newer, Python 3 and a checkout of SFP (the SFP installer records it in `~/.sfp/root`).

```bash
python3 extensions/antigravity-hive/install.py
```

It installs the dependencies, runs the tests, builds `sfp-hive-0.1.0.vsix` and installs it with the editor's own command (`antigravity --install-extension`, or `code`, `cursor`, `windsurf`) for each one it finds on `PATH`. If none is found it prints the manual steps: Extensions view, the `...` menu, **Install from VSIX...**. Then reload the window. The `antigravity` command name is the usual one for VS Code forks, and is not confirmed here; the manual route always works.

## Use

- **Status bar, "Hive"** or **SFP Hive: Choose skills for a task** in the command palette: type the task. The hive reads your open workspace's files and chooses up to `sfpHive.maxSkills` skills.
- **SFP Hive view** (activity bar): the skills grouped as Base, Check and Finish, with the reasons on hover. Click a skill to open its `SKILL.md`.
- **The prompt** is copied to the clipboard after choosing (turn off with `sfpHive.copyPromptAfterChoosing`). Paste it into the agent panel. The extension does not type into the agent panel itself, because no public API for that was confirmed.
- **Feedback**: the thumbs-up, thumbs-down and circle-slash buttons on each skill record `helped`, `unhelpful` and `ignored`; the `+` in the view title records a `missing` skill. This is what the hive learns from.
- **Install SFP skills into this workspace**, **Add the standing hive instruction** and **Set up a program a skill needs** open a terminal with the matching `install.py` command. They show the plan and leave the final `--yes` to you.

Settings: `sfpHive.sfpPath`, `sfpHive.python`, `sfpHive.maxSkills`, `sfpHive.copyPromptAfterChoosing`, `sfpHive.installTool` (the installer tool name, `antigravity` by default, `copilot` for VS Code).

## How it is built

| File | Job |
|---|---|
| `src/hive.ts` | No editor code. Finds the checkout, builds the command lines, runs the hive without a shell, parses its JSON, builds the prompt. Unit tested. |
| `src/extension.ts` | The glue: status bar, tree view, commands, terminal. |
| `test/hive.test.js` | The pure parts and a real end-to-end run of the hive and its feedback log. |
| `test/extension.test.js` | Loads the real extension against a stand-in for the `vscode` module and drives it. |
| `test/e2e/` | Drives a real VS Code in a headless browser (needs code-server). |
| `install.py` | Build, test, package, install. |

`npm test` inside the folder runs 21 tests, with the editor API stood in. `test/e2e/drive.js` goes further: it drives a real VS Code (code-server 4.117.0, VS Code 1.117.0) in a headless browser with the extension installed, and checks that it activates at startup, the command is in the palette, choosing skills lists them, the status bar counts them, the prompt is copied and feedback is recorded. That run found one bug (no status-bar item until first use), now fixed. What has not been run: the extension inside Antigravity itself, because the editor is not available where this was built. It uses only the standard extension API that Antigravity shares with VS Code, so it should behave the same, but that is an expectation, not a test.

## Check that it runs in Antigravity

The extension adds its own activity-bar view, status-bar item and commands. It does not add itself inside the agent chat window; it copies a prompt that you paste there. So "appearing" means the things below, and the last check is the one that matters: the agent acting on the prompt.

### 1. The prompt for Antigravity's agent

Open the SFP checkout as the workspace, open the agent window, and paste this. The agent can run commands, so it does the command-line half and then asks you for the on-screen half.

> You are checking that the SFP Hive extension works in this Antigravity. Do not modify Antigravity's own files; only run the commands below and report what they print.
>
> 1. In the terminal, from the SFP checkout, run `python3 extensions/antigravity-hive/install.py`. Show me the last 15 lines. If it says no editor command was found, tell me and stop: I will install the `.vsix` by hand from the Extensions view.
> 2. Run `python3 extensions/antigravity-hive/verify.py --json` and show me the complete JSON.
> 3. Ask me to run "Developer: Reload Window" and wait until I say it is done. You cannot do this yourself.
> 4. Run `verify.py --json` again and show the complete output.
> 5. Ask me the on-screen questions V1 to V8 from the checklist below, one line each, and wait for my answers. Do not guess any of them.
> 6. Then write the report: a table with one row per check (the M checks from the JSON, then V1 to V8), each marked PASS, FAIL or WARN with one line of evidence, and a final verdict from the scoring rule below. For every FAIL, name the most likely cause from the troubleshooting table and the exact command or setting that fixes it.

### 2. The checks

Machine checks (`verify.py`, exit code 1 on any FAIL):

| ID | Check |
|---|---|
| M1 | The editor's command is on `PATH`, and the editor is VS Code 1.85 or newer |
| M2 | The editor lists `siddu1004.sfp-hive` |
| M3 | The extension folder exists, activates at startup and has its code |
| M4 | An SFP checkout is found and the hive answers with at least one skill |
| M5 | The feedback log folder is writable |
| M6 | The editor's extension-host logs show no error mentioning the extension |

On-screen checks, which you answer yes or no (do V1 to V3 once before installing as a control; they should all be no):

| ID | Look at | Expected |
|---|---|---|
| V1 | The activity bar (left edge) | A hexagon icon, "SFP Hive" on hover |
| V2 | The status bar (bottom left), right after a reload and before you use anything | An item reading "Hive" |
| V3 | The command palette, typing "SFP Hive" | Seven commands (the four buttons on each skill are hidden from the palette) |
| V4 | Run "Choose skills for a task" with `write table driven tests for a go parser` | The SFP Hive view lists at least one skill under Base, Check or Finish, the status bar reads "Hive: N", and a message says the prompt is copied |
| V5 | Paste the clipboard into the agent window and send it | The agent names the listed skills and opens their `SKILL.md` files before it answers |
| V6 | Click the thumbs-up on a skill | The status bar says "noted helped", and `~/.sfp/feedback.jsonl` gains a line with that skill |
| V7 | Click a skill's name | Its `SKILL.md` opens |
| V8 | Settings, searching "SFP Hive" | Five settings |

### 3. Scoring

- **Installed**: M1 to M3 all pass.
- **Running**: Installed, and V1, V2, V3 pass, with no FAIL in M4 to M6.
- **Working**: Running, and V4, V6 and V7 pass.
- **Used by the agent**: Working, and V5 passes. This is the result that shows the extension changes what the agent does. If V5 fails while V4 passes, the extension works and the agent ignored the prompt; try the standing instruction (`install.py rules --project .`) and compare.

A before-and-after check is stronger than one run: do V5 with the prompt and again with the same task and no prompt, and compare which skills the agent opens.

### 4. If a check fails

| Symptom | Likely cause | Fix |
|---|---|---|
| M1 fails | The editor's shell command is not installed | In the editor run "Shell Command: Install command in PATH", or install the `.vsix` from the Extensions view (`...` menu, Install from VSIX) |
| M2 or M3 fails after install | The install ran in a different editor, or needs a reload | Run `install.py --editor antigravity`, then reload the window |
| M3 says no startup activation | An older build is installed | Rebuild and reinstall with `install.py` |
| Editor too old | Its VS Code base is older than 1.85 | Update the editor, or lower `engines.vscode` in `package.json` and rebuild |
| V1 passes, V2 fails | Old build without startup activation | Reinstall |
| V1 fails, M3 passes | The icon is hidden | Right-click the activity bar and tick "SFP Hive" |
| V4 says it could not find your SFP checkout | `~/.sfp/root` is missing | Set `sfpHive.sfpPath` to the checkout folder |
| V4 says it could not start python3 | Python is not named `python3` | Set `sfpHive.python` |
| V6 shows "Feedback is off" | `SFP_NO_USAGE_LOG` is set in the editor's environment | Unset it, restart the editor |
| M6 fails | The log line names the cause | Send me that line |

Send the agent's report back and I will fix whatever it shows.

## A visible button to see and steer the choice

[HIVE-INSPECTOR.md](HIVE-INSPECTOR.md) is the build brief and prompt for the Hive Inspector: a status-bar button under the agent window that shows the chosen skills, every candidate that was considered with its signal votes and the reason it was dropped, and lets you remove, add and re-choose, with the change sent back as feedback. The hive side (`--explain`, `--include`, `--exclude`) is built and tested.

## Implementation prompts

Paste these into your agent, one at a time, from the SFP checkout. Each ends with how to tell it worked.

**1. Verify the build in your editor.**
> In `extensions/antigravity-hive`, run `python3 install.py`. Then open Antigravity, reload the window, and check that an SFP Hive icon appears in the activity bar and a "Hive" item in the status bar. Run "SFP Hive: Choose skills for a task" with "add tests for a Go parser". Report exactly what happens, and any error from Help > Toggle Developer Tools. Done when a list of skills appears and the prompt is on the clipboard.

**2. Put the prompt into the agent panel.**
> Antigravity's agent panel has no documented way to receive text from an extension. Find out what the editor exposes, using only public routes: open the command palette and search "agent", "chat" and "prompt"; read the editor's own documentation; and read the list of contributed commands under Help > Toggle Developer Tools. If a command accepts a prompt, add it to `src/extension.ts` behind a setting `sfpHive.sendToAgent`, with a fallback to the clipboard when the command is missing. Do not read or copy the editor's installed source files. Done when the setting sends the prompt to the panel, and the clipboard fallback still works with the setting off.

**3. Choose automatically from the agent's own request.**
> Add a command that takes the text selected in the editor as the task and runs the hive on it, bound to a key you propose in `package.json`. Add a test in `test/extension.test.js`. Done when selecting a sentence and pressing the key fills the tree.

**4. A browser for all skills.**
> Add a second view "All skills" that lists every category from `catalog.json` with its skills, searchable by the view's built-in filter, and a context action "Choose this skill" that adds it to the current selection as a `missing` report. Keep it read-only: it reads `catalog.json` and never writes into the checkout. Done when you can find `react-three-fiber` and open its `SKILL.md`.

**5. Learning status panel.**
> Replace "Show what the hive has learned" (it opens a terminal) with a view that runs `python3 mcp/sfp_hive.py status` and shows the number of decisions, the judged share and the skills with the most positive and negative preference. Done when the numbers match the terminal output.

**6. An OmniRoute panel.**
> Using the existing `apps/sfp_app.py status omniroute`, add a status-bar item that shows whether OmniRoute is installed and running, with actions to show the install plan and to start it. Never run an install without the user confirming in a prompt that shows the plan. Done when the item changes colour when the gateway at `http://localhost:20128` starts and stops.

**7. Publish to Open VSX.**
> Add a `docs/PUBLISHING.md` that explains how to create an Open VSX namespace and token and publish with `npx ovsx publish sfp-hive-*.vsix -p <token>`. Do not put a token in the repository or in any command you run. Done when the steps are written, and a dry run of `vsce package` succeeds.

## Limits

- It has been run in VS Code 1.117 (through code-server) but not in Antigravity. Treat the first run there as a test and send back what breaks.
- It needs Python 3 and an SFP checkout on the same machine as the editor. In a remote or container workspace, the extension runs where the workspace runs, so SFP must be installed there.
- It selects and records feedback; it does not run the skills. The agent panel does that.
