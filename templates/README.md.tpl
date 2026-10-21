<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img src="assets/banner-light.svg" alt="SFP: Skills for Productivity" width="100%">
  </picture>
</h1>

<p align="center">
  <b>SFP gives your AI coding agent @@TOTAL@@ skills, sorted by what you build.</b><br>
  Install a handful. One skill, <code>sfp</code>, finds the rest.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/skills-@@TOTAL@@-0f766e?style=flat-square&labelColor=3b4350" alt="@@TOTAL@@ skills">
  <img src="https://img.shields.io/badge/works_in-16_IDEs-0f766e?style=flat-square&labelColor=3b4350" alt="Works in 16 IDEs and CLIs">
  <img src="https://img.shields.io/badge/installer-Python_3_only-0f766e?style=flat-square&labelColor=3b4350" alt="Installer needs only Python 3">
  <img src="https://img.shields.io/badge/licenses-MIT_and_Apache--2.0-0f766e?style=flat-square&labelColor=3b4350" alt="MIT and Apache-2.0 licenses">
</p>

## Quick Start

Install the starter set into every IDE it finds (macOS and Linux):

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh
```

Restart your IDE, then give your agent a task. `sfp` picks the skill.

On Windows or in Claude Code? See [Windows](#windows) and [Claude Code](#claude-code). For presets and single IDEs, see [all install options](#install).

## How It Works

A skill is a folder with a `SKILL.md` that an agent loads when a task matches.

Agents read the description of every installed skill when a session starts. @@TOTAL@@ descriptions is too many to carry. So you install `sfp` plus the categories you use daily, and `sfp` handles the rest:

```mermaid
flowchart LR
    task([Your task]) --> sfp[[sfp skill]]
    sfp --> index[Searches the index of @@TOTAL@@ skills]
    index --> installed{Installed?}
    installed -- yes --> use([Uses the skill])
    installed -- no --> read[Reads it from the SFP checkout]
    read --> use
    classDef key fill:#0f766e,stroke:#0f766e,color:#ffffff
    class sfp key
```

In words: `sfp` searches an index of every skill. If the skill is installed, your agent uses it. If not, `sfp` reads it straight from this checkout. The installer saves the checkout path in `~/.sfp/root` so it can.

What you get:

- **Skills sorted by what you build.** @@NCATS@@ categories, from frontend and backend to security and agents.
- **One install line for 16 IDEs and CLIs.** Claude Code gets plugins. Every other tool gets plain skill folders.
- **Presets.** Pick `frontend-dev`, `backend-dev`, `mobile-dev` or `agent-builder`, or take them all.
- **Safe installs.** The installer only touches folders it created. Your own skills stay as they are.
- **A free API finder.** Your agent can search about 2,100 APIs and filter by auth, HTTPS and CORS.

## Install

Everything needs `git`. Outside Claude Code's plugin route it also needs Python 3.

### macOS and Linux

Choose what to install:

```bash
# Everything, into every IDE found
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --profile everything

# One IDE, one preset
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --tools cursor --profile frontend-dev
```

### Windows

In PowerShell:

```powershell
irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1 | iex
```

To choose what to install:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1))) --tools cursor --profile frontend-dev
```

### Claude Code

Run these inside Claude Code:

```text
/plugin marketplace add siddu1004/SFP
/plugin install sfp@sfp
/plugin install frontend@sfp
```

Replace `frontend` with any category from the [category list](#pick-a-preset). Plugins update with `/plugin update`.

### From a clone

<details>
<summary>Read the installer first, then run it</summary>

```bash
git clone https://github.com/siddu1004/SFP.git && cd SFP
./install.sh list                                  # categories, presets, tools found
./install.sh --profile backend-dev                 # a preset
./install.sh --categories security,devops,memory   # exact categories
./install.sh --tools cursor,codex                  # only these tools
./install.sh --project .                           # into this project's tool folders
./install.sh --link                                # symlink, so git pull updates skills (macOS, Linux)
./install.sh uninstall --tools cursor              # remove what it installed
```

On Windows, use `.\install.ps1` in place of `./install.sh`.
</details>

### Let your agent install it

<details>
<summary>Paste this prompt into any agent</summary>

> Clone https://github.com/siddu1004/SFP, run its `install.sh` (or `install.ps1` on Windows) with `--tools <this tool>`, then restart me so the skills load.
</details>

To update, run the same install line again. The installer replaces only folders it created. A skill you made with the same name stays unless you add `--force`.

## Pick a Preset

@@PRESET_TABLE@@

<details>
<summary>All @@NCATS@@ categories</summary>

@@CATEGORY_TABLE@@

`ecc-full` and `omniroute-full` add the hooks, agents and commands of Everything Claude Code and OmniRoute. Their skills are already in the categories above, so install the full plugin or the categories, not both.
</details>

## Supported IDEs

Claude Code, Codex, Cursor, Gemini CLI, Antigravity, GitHub Copilot, Windsurf, Kiro, OpenCode, Pi, Grok Build, Qoder, Trae, Rovo Dev, Mistral Vibe and Hermes.

Name them with `--tools`:

```text
claude codex cursor gemini antigravity copilot windsurf kiro opencode pi grok qoder trae rovodev vibe hermes
```

<details>
<summary>Where each tool keeps its skills</summary>

| Tool | Your home folder | A project (`--project`) |
|---|---|---|
| Claude Code | `~/.claude/skills` (or plugins) | `.claude/skills` |
| Codex | `~/.agents/skills` | `.agents/skills` |
| Cursor | `~/.cursor/skills` | `.cursor/skills` |
| Gemini CLI | `~/.gemini/skills` | `.gemini/skills` |
| Antigravity | `~/.gemini/config/skills` | `.agent/skills` |
| GitHub Copilot | `~/.copilot/skills` | `.github/skills` |
| Windsurf | `~/.codeium/windsurf/skills` | `.windsurf/skills` |
| Kiro | `~/.kiro/skills` | `.kiro/skills` |
| OpenCode | `~/.config/opencode/skills` | `.opencode/skills` |
| Pi | `~/.pi/agent/skills` | `.pi/skills` |
| Grok Build, Qoder, Trae, Rovo Dev, Vibe, Hermes | `~/.<tool>/skills` | `.<tool>/skills` |

A tool counts as found when its home folder exists, for example `~/.cursor`. Use `--tools` to install into one that is not found yet.

I could not confirm the Windsurf and Copilot paths against their docs. If one is wrong for your version, fix it in the `TOOLS` table in `scripts/install.py`.
</details>

## Free APIs

The `public-apis` skill bundles a list of about 2,100 free APIs in 51 categories, plus a search script. Your agent can run it directly:

```bash
python3 plugins/data-apis/skills/public-apis/scripts/find_api.py weather --auth none --cors yes
python3 plugins/data-apis/skills/public-apis/scripts/find_api.py --category Finance --limit 10
python3 plugins/data-apis/skills/public-apis/scripts/find_api.py --categories
```

Filters: `--auth none|apiKey|OAuth`, `--cors yes|no`, `--https yes|no` and `--json`. It needs only Python 3.

## Good to Know

- **career** runs from its own checkout in `~/.sfp/apps/career-ops`. Run `npm install` there once. Your CV, tracker and reports live in `~/career-ops`, so updates never touch them.
- **session-memory** needs Claude Code's hooks and a background worker, so other IDEs skip it. The `memory` skills expect claude-mem, so most need it installed.
- **ai-gateway** skills drive an OmniRoute server. **security** skills drive the Strix CLI. Each skill explains how to set up what it needs.
- **Impeccable** (in `frontend`) downloads its engine on first use.

## Keep It Fresh

Pull the latest skills from every source into SFP, then commit the result:

```bash
python3 scripts/sync.py            # rebuild the plugins, catalog, README and banner
python3 scripts/sync.py --report   # also show what each category got
```

- **Add a source:** add an entry to `sources.json` with `repo`, `license`, a `default` category and `skills` paths, then sync.
- **Move a skill:** add its name to `names` in `categories.json`, or adjust a pattern, then sync.
- **Add a category:** add it under `categories` in `categories.json`. Names cannot start with `claude-` or `anthropic-`.

The README, banner, `plugins/`, `catalog.json` and `SKILLS.md` are generated. Edit `templates/README.md.tpl` and the JSON files, not the outputs.

## Sources and Licenses

Each skill keeps the license of the project it came from. [NOTICE.md](NOTICE.md) lists every source, and each category folder holds copies of its licenses in `plugins/<category>/LICENSES/`. The full skill list is in [SKILLS.md](SKILLS.md).

<details>
<summary>Where every source landed (@@SOURCES@@ sources)</summary>

Every skill in these repos is in SFP, except test fixtures and translated example copies. Repos with no skill of their own got one written for them. Plugins with no public repo are kept as snapshots in `vendor/`.

| Source | Where it is in SFP |
|---|---|
| impeccable | `frontend`: Impeccable, 24 design commands |
| taste-skill-for-claude-and-antigravity | `frontend`: the Taste skills |
| skills-claude-antigravity | `frontend`: Emil Kowalski's skills |
| vercel-labs/web-interface-guidelines | `frontend`: a UI review checklist |
| design-skills | `frontend`: 10 UX design skills |
| awesome-design-skills | `design-styles` |
| strix | `security` |
| claude-plugins-official | `agent-dev` and others: every skill it ships. Its other plugins point to third-party repos |
| ECC | spread across `agents`, `agent-dev`, `backend`, `frontend`, `testing-quality` and more |
| OmniRoute | `ai-gateway`, plus 6 maintenance skills in `devops` |
| claude-mem | `memory`, and the optional `session-memory` plugin |
| Agent-Reach | `data-apis` |
| public-apis | `data-apis`: a searchable skill over about 2,100 free APIs |
| freellmapi | `data-apis`: a skill with the project's docs |
| MoneyPrinterTurbo | `content-media` |
| marketing-psychology | `content-media`: 5 persuasion and behavior skills |
| Anthropic example skills | 8 Apache-2.0 skills: algorithmic art, brand guidelines, canvas design, internal comms, MCP builder, Slack GIF creator, theme factory, web artifacts builder |
| teach-me | `research-docs` |
| task-observer, headroom | `agent-dev` |
| cowork-plugin-management | `agent-dev` |
| gia-chief-of-staff | `business-ops` |
| career-ops | `career`, installed from its own repo |

**Left out on purpose:** anything whose license does not allow republishing. That covers Greenhouse's customer-only plugin, Anthropic's docx, pdf, pptx, xlsx and browser skills (all rights reserved), and the noncommercial-only `claude-mem-cowork` plugin.
</details>
