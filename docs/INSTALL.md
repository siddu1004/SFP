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

## Quickest install (Windows, macOS, Linux)

If you have Node.js 18+ and Python 3:

```bash
# Via GitHub Packages (zero cloning needed):
npx --registry=https://npm.pkg.github.com @siddu1004/sfp install
```

This bootstraps SFP into `~/.sfp/SFP` and installs the starter skills into every detected tool in one command. For manual step-by-step setup, continue below.

## 1. Get SFP

### Option A: Via GitHub Packages / npx
```bash
npx --registry=https://npm.pkg.github.com @siddu1004/sfp install
```

### Option B: Clone the Repository
```bash
git clone https://github.com/siddu1004/SFP.git
cd SFP
```

### Option C: Via Cargo (Rust)
```bash
cargo install --git https://github.com/siddu1004/SFP.git
sfp install
```

**Check your environment in 5 seconds:**
```bash
# macOS / Linux
python3 mcp/sfp_hive.py doctor

# Windows (PowerShell / Command Prompt)
python mcp/sfp_hive.py doctor
```
*(Prints a full health report across Python, catalog, index, selection, and tools).*

## 2. Install the skills into your tools

```bash
# Small curated starter set into every tool found on your machine
python3 scripts/install.py install --profile starter

# Or view all categories and presets
python3 scripts/install.py list
```

Restart your agent tools. Check: ask your agent:
> *"Use sfp-hive for this task: add tests for the checkout form."*

It should name a few skills that fit your exact project stack, say why, and follow them in order.

### Universal MCP Server (for Claude Code, Cursor, Antigravity & Windsurf)
To give tools without a dedicated skills folder access to the entire 819-skill library:

```bash
python3 scripts/install.py mcp
```

## 3. Install the SFP Hive editor extension (the sidebar)

From the `SFP` folder:

```bash
# macOS / Linux
python3 extensions/antigravity-hive/install.py

# Windows (PowerShell)
python extensions/antigravity-hive/install.py
```

It builds and tests the extension, packages a `.vsix` and installs it into every editor it finds (`antigravity`, `code`, `cursor`, `windsurf`). If you downloaded a `.vsix` from a GitHub release: open your editor's Extensions view, click the "..." menu, select **Install from VSIX...**, and choose the file.

Then reload your editor window (Ctrl+Shift+P / Cmd+Shift+P → *"Developer: Reload Window"*).

**Check:** The SFP Hive icon appears in the activity bar. Open it, navigate to **Insights**, and click **Check connection**: all indicators will display green.

## 4. Automatic skills (zero copy-paste)

This is enabled by default. When you choose a task in **Choose**, or the **Now** tab tracks your progress into a new phase (design, build, test, debug, review), the extension automatically updates `.agents/rules/sfp-active-skills.md` in your workspace. 

Your coding agent reads this rule file on every turn, giving it the exact skills needed without manually typing or copying prompts.

## 5. Local Model Router (127.0.0.1:8787) — Work Past Cloud Limits

SFP includes an OpenAI-compatible model router that prioritizes your local models (LM Studio, Ollama, llama.cpp), fails over automatically across free and cloud tiers, and protects you from 429 rate limits:

```bash
# 1. Discover running local runtimes
python3 mcp/sfp_route.py discover

# 2. Setup model routes and cloud keys
python3 mcp/sfp_route.py setup --yes

# 3. Start the router server
python3 mcp/sfp_route.py serve
```

### Point any tool to the router:
- **Base URL**: `http://127.0.0.1:8787/v1`
- **API Key**: Any string (e.g. `sfp` or `local`)
- **Model**: `auto` (or `sfp/light`, `sfp/normal`, `sfp/heavy`)

Supported clients:
- **VS Code / Cursor / Windsurf / Antigravity**: Set as custom OpenAI provider.
- **Cline / Continue / Roo Code**: Base URL `http://127.0.0.1:8787/v1`.
- **Aider / OpenCode / Custom Python scripts**: Standard OpenAI client pointing to port 8787.

Local models take the load first. When one model is cooling down or rate limited, the router seamlessly delegates the request to the next available provider.

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
