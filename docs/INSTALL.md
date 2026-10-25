# Installing SFP

This guide takes you from nothing to an agent that gets the right skills automatically. Each step ends with a check, so you know it worked before you go on. Allow about ten minutes.

## What you need

| | Why | Check |
|---|---|---|
| Python 3.8 or newer | runs the hive, the router and the checks | `python --version` |
| Git | gets SFP and keeps it current | `git --version` |
| Node.js 18 or newer and npm | only to build the editor extension | `node --version` |
| An editor: Antigravity, VS Code, Cursor or Windsurf | for the SFP Hive sidebar | |
| Optional: Ollama or LM Studio | local models for the router | |

On Windows, use `python` where this guide says `python3`.

## 1. Get SFP

```bash
git clone https://github.com/siddu1004/SFP.git
cd SFP
```

Check: `python3 mcp/sfp_hive.py doctor` prints a list ending in "Everything is connected" or "Working, with things to look at". Router lines may warn for now; that is fine.

## 2. Install the skills into your tools

```bash
python3 scripts/install.py install --profile starter   # a small set into every tool it finds
python3 scripts/install.py list                        # the categories and presets, if you want more
```

Restart your agent tools. Check: ask your agent "Use sfp-hive for this task: add tests for the checkout form." It should name a few skills and say why.

To give tools without a skills folder the whole library, register the MCP server:

```bash
python3 scripts/install.py mcp
```

## 3. Install the SFP Hive extension (the sidebar)

The quickest way, from the SFP folder:

```bash
python3 extensions/antigravity-hive/install.py
```

It builds and tests the extension, packages a `.vsix` and installs it into every editor it finds (`antigravity`, `antigravity-ide`, `code`, `cursor`, `windsurf`). If none is on your PATH, or you downloaded a `.vsix` from a release, install it by hand: open the editor's Extensions view, "..." menu, "Install from VSIX...", pick the file.

Then reload the window (Ctrl+Shift+P, "Developer: Reload Window").

If the sidebar says the checkout cannot be found, set the setting **SFP Hive: Sfp Path** (`sfpHive.sfpPath`) to your SFP folder.

Check: the SFP Hive icon is in the activity bar. Open it, go to **Insights**, press **Check connection**: every line except the router ones should be green.

## 4. Let the agent get its skills automatically

This is on by default. When you choose a task in **Choose**, or the **Now** tab follows your work into a phase, the extension writes the chosen skills to `.agents/rules/sfp-active-skills.md` in your workspace. Antigravity's agent reads that folder on every turn.

Check: choose a task, then ask the agent "Which skills are active for this task?". It should list the same skills as the sidebar. **Insights → Skill history** shows what was given for which prompt.

Turn it off with the command "SFP Hive: Turn automatic skills on or off"; then use **Copy prompt** by hand. Add `.agents/rules/sfp-active-skills.md` to your project's `.gitignore` if you do not want it committed.

## 5. Optional: use your local models, and keep working past limits

Start Ollama or LM Studio with a model loaded, then:

```bash
python3 mcp/sfp_route.py discover        # lists the local models it finds
python3 mcp/sfp_route.py setup --yes     # writes ~/.sfp/routes.json (adds cloud providers whose keys are set)
python3 mcp/sfp_route.py serve           # leave this running
```

Point any OpenAI-compatible tool (Cline, Continue, Codex, Aider, your scripts) at `http://127.0.0.1:8787/v1`, any key, model `auto`. Local models go first; when one is rate limited or down, the next answers. Models you start later are found within 30 seconds.

Check: `python3 mcp/sfp_hive.py doctor` shows "Router running: N of N models ready". The router cannot redirect an editor's own built-in agent; [ROUTER.md](ROUTER.md) explains the limits.

## 6. Optional: turn a Git repository into a skill

In the Library tab, press **+** at the bottom and paste a repository URL, `owner/repo` or a folder. Or:

```bash
python3 scripts/repo_to_skill.py https://github.com/owner/repo --install antigravity
```

The skill is written from the repository's README (or by your strongest local model, if one is running) to `~/.sfp/skills/<name>/` and copied into the tool you name.

## Keeping it current

```bash
git pull
python3 extensions/antigravity-hive/install.py     # rebuild and reinstall the extension after an update
python3 mcp/sfp_hive.py doctor
```

## When something is wrong

| You see | Do this |
|---|---|
| "SFP checkout not found" | Set `sfpHive.sfpPath` to the SFP folder, reload the window |
| Search index: stale | `python3 scripts/sync.py`, or `git pull` (fixed for Windows line endings in 3.16.1) |
| The Library tab stays on "Loading" | Update to 0.3.0 of the extension and reload |
| The agent names other skills than the sidebar | Choose the task again; check `.agents/rules/sfp-active-skills.md` exists in the workspace and automatic skills are on |
| Router running: not running | `python3 mcp/sfp_route.py serve` in a terminal you leave open |
| Local models: none found | Start Ollama (port 11434) or LM Studio's server (port 1234) |
| Anything else | `python3 mcp/sfp_hive.py doctor` names the failing part and the command that fixes it |

## Removing it

```bash
python3 scripts/install.py uninstall      # removes only what SFP installed
```

Uninstall the extension from the editor's Extensions view. Your history and settings are in `~/.sfp`; delete that folder to remove them.
