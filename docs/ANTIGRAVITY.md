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
| `install.py` | Build, test, package, install. |

`npm test` inside the folder runs 18 tests. What has not been run: the extension inside Antigravity itself, because the editor is not available where this was built. The glue is tested against a stand-in, not the real thing, so expect to fix small differences on first run.

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

- It has not been run in Antigravity. Treat the first run as a test and send back what breaks.
- It needs Python 3 and an SFP checkout on the same machine as the editor. In a remote or container workspace, the extension runs where the workspace runs, so SFP must be installed there.
- It selects and records feedback; it does not run the skills. The agent panel does that.
