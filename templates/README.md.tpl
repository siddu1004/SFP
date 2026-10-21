<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img src="assets/banner-light.svg" alt="SFP: Skills for Productivity" width="100%">
  </picture>
</h1>

<p align="center">
  <b>Give your AI coding agent the right skills for the job, not all of them.</b><br>
  @@TOTAL@@ skills, sorted by what you build. Two small skills pick the few each task needs, for the project in front of them.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-@@HIVE_VERSION@@-0f766e?style=flat-square&labelColor=3b4350" alt="Version @@HIVE_VERSION@@">
  <img src="https://img.shields.io/badge/skills-@@TOTAL@@-0f766e?style=flat-square&labelColor=3b4350" alt="@@TOTAL@@ skills">
  <img src="https://img.shields.io/badge/installs_into-16_IDEs-0f766e?style=flat-square&labelColor=3b4350" alt="Installs into 16 IDEs and CLIs">
  <img src="https://img.shields.io/badge/tested_end_to_end-Claude_Code-0f766e?style=flat-square&labelColor=3b4350" alt="Tested end to end in Claude Code">
  <img src="https://img.shields.io/badge/needs-Python_3-0f766e?style=flat-square&labelColor=3b4350" alt="Needs Python 3">
  <img src="https://img.shields.io/badge/license-MIT-0f766e?style=flat-square&labelColor=3b4350" alt="MIT license">
</p>

## Try It in 60 Seconds

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh
```

That installs the starter set into every IDE it finds (macOS and Linux). On Windows or in Claude Code, see [Install](#install). Restart your IDE, then ask your agent:

> Use sfp-manager for this task: add tests for the checkout form.

It should name the few skills that fit your project, say why, and follow them in order.

**Not for you?** Undo it with one line: `~/.sfp/SFP/install.sh uninstall`. It removes only what it installed.

## The Problem

Good agent skills exist, but they are scattered across dozens of repos, each with its own install steps and folder layout. And installing many of them costs more than it looks.

- **Agents typically read every installed skill's description at the start of every session.** For this library that is about @@ALL_TOKENS@@ tokens, or @@ALL_PERCENT@@% of a 200k window, before you type a word.
- **So you choose between two bad options.** Install a few skills and miss the good ones, or install many and pay for a catalog you rarely use.
- **Picking by hand is guesswork.** The skill for "write tests" is a different skill in a Next.js app, a Django app and a Rust crate.

## What SFP Does

| Move | How | What it gives you |
|---|---|---|
| **Sort** | @@SOURCES@@ sources merged into @@NCATS@@ categories, grouped by what you build; presets group categories by role | A backend developer finds Postgres, migrations, API design and Docker together |
| **Route** | `sfp` finds a skill; `sfp-manager` runs a hive that picks the few a task needs, in order | About @@SFP_TOKENS@@ tokens of descriptions instead of @@ALL_TOKENS@@: @@RATIO@@ times less |
| **Install once** | One command writes each of 16 IDEs' skills folders; the MCP server serves the same library to tools with no skills folder | No hunting for formats and paths |

Every skill keeps its original license and author. SFP reads the original projects, and `sources.lock.json` pins the exact commit of each.

## See It Choose

The same words, "write tests for the orders", in five different projects. This is real output from the hive, regenerated each time this page is built:

@@SAME_WORDS_TABLE@@

Plain search gives the same answer in all five. The hive reads each project's files (`package.json`, `Cargo.toml`, `pubspec.yaml`, `requirements.txt` and so on), so a Django skill is not offered for a React app. Across all three task sets below, @@WRONG_HIVE@@ stacks held a skill for the wrong technology.

It is not perfect, and the examples show it: `django-celery` joins the Django stack because the project uses Celery and its description mentions tests. A strong general skill such as `application-security-testing` sometimes joins as filler. The [proof](#the-proof) below says how often it is right and where it is not.

## The Proof

Everything here is computed from this repository when the README is rebuilt. Run `python3 mcp/sfp_hive.py evaluate` to reproduce it.

**Does it pick the right skill?** "Right" means the stack holds a skill that a person marked as correct for the task. Plain search gets about as many results as the hive's average stack.

| Task set | Hive @@HIVE_VERSION@@ | Previous engine | Plain search |
|---|---:|---:|---:|
| @@FRESH_N@@ new tasks in 8 new projects, written before the hive and scored once | **@@FRESH_HIVE@@** | @@FRESH_V1@@ | @@FRESH_SEARCH@@ |
| @@PROJ_N@@ tasks in 10 sample projects | @@PROJ_HIVE@@ | @@PROJ_V1@@ | @@PROJ_SEARCH@@ |
| @@BENCH_N@@ tasks with no project | @@BENCH_HIVE@@ | @@BENCH_V1@@ | @@BENCH_SEARCH@@ |
| Stacks with a skill for the wrong technology, all sets | @@WRONG_HIVE@@ | @@WRONG_V1@@ | @@WRONG_SEARCH@@ |

**What does it cost your agent?** Every installed skill puts its name and description into each session, at about 4 characters per token.

@@COST_TABLE@@

With `sfp` and the MCP server you still reach every skill, and you pay for a skill's full text only when it is used: a median of about @@BODY_MEDIAN@@ tokens, and 90% are under @@BODY_P90@@. A hive stack averages @@BENCH_HIVE_SIZE@@ skills when there is no project.

**How fast is it?** About @@HIVE_MS@@ ms per decision, inside the process that asks, once per phase of work. A call through the running MCP server takes 3 to 5 ms once the project has been scanned. [docs/HIVE.md](docs/HIVE.md#speed) has the before and after.

> **What has not been measured.** Whether stacks make your agent's finished work better. I have not run a benchmark of real tasks with and without SFP, so these figures show cost and choice, not quality of results. The tasks and their correct answers were written by one person. The hive's settings were tuned on the 10-project and no-project sets, so those rows are optimistic; the new set was written first and opened once. Token counts are an estimate (characters divided by 4). Search is keyword-based, so a task that shares no words with the right skill can miss it: "scrape product prices" does not surface `data-scraper-agent`.

## Who It Is For

| You are | Install | You get, for example | Try asking |
|---|---|---|---|
| A frontend developer | `frontend-dev` | `impeccable`, `design-taste-frontend`, `animate`, `accessibility-audit`, `break-ui` | "Critique this page and fix the hierarchy." |
| A backend developer | `backend-dev` | `postgres-patterns`, `database-migrations`, `api-design`, `docker-patterns`, `tdd-workflow` | "Plan a zero-downtime migration for this table." |
| A mobile developer | `mobile-dev` | `swiftui-patterns`, `dart-flutter-patterns`, `android-clean-architecture`, `compose-multiplatform-patterns` | "Review this Flutter screen for state-management problems." |
| Building agents, plugins or MCP servers | `agent-builder` | `skill-creator`, `hook-development`, `mcp-builder`, `agent-eval`, `mem-search` | "Help me design an MCP server for our ticket system." |
| Security-minded | `backend-dev` and `security` | `penetration-testing-with-strix`, `owasp-top-10-testing`, `find-security-vulnerabilities-in-code`, `security-review` | "Check this service against the OWASP top 10." |
| A founder or marketer | `business-ops` and `content-media` | `investor-materials`, `marketing-campaign`, `article-writing`, `persuasion-audit`, `price-framing` | "Draft this month's investor update." |
| Job hunting | `career` | `career-ops` | "Evaluate this job posting against my CV." |
| Using an IDE with no skills folder | the MCP server | every skill, through `search_skills` and `get_skill` | "Search SFP for a skill that fits this task." |

## Install

You need `git`, and Python 3 outside Claude Code's plugin route.

<details open>
<summary><b>macOS and Linux</b></summary>

```bash
# The starter set, into every IDE found
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh

# One IDE, one preset
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --tools cursor --profile frontend-dev

# Everything (it costs about @@ALL_PERCENT@@% of your context in descriptions)
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --profile everything
```
</details>

<details>
<summary><b>Windows</b></summary>

In PowerShell:

```powershell
irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1 | iex
```

To choose what to install:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1))) --tools cursor --profile frontend-dev
```
</details>

<details>
<summary><b>Claude Code</b></summary>

Run these inside Claude Code:

```text
/plugin marketplace add siddu1004/SFP
/plugin install sfp@sfp
/plugin install frontend@sfp
```

Replace `frontend` with any category from the [presets and categories](#pick-a-preset). Plugins update with `/plugin update`.
</details>

<details>
<summary><b>From a clone, to read the installer first</b></summary>

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

<details>
<summary><b>Let your agent install it</b></summary>

Paste this into any agent:

> Clone https://github.com/siddu1004/SFP, run its `install.sh` (or `install.ps1` on Windows) with `--tools <this tool>`, then restart me so the skills load.
</details>

To update, run the same install line again. The installer replaces only folders it created. A skill of yours with the same name stays unless you add `--force`.

**Want every skill without installing any?** Add the MCP server, which lets any MCP client search and read the whole library on demand:

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- mcp
```

It registers `sfp` in each IDE it finds and keeps your other MCP servers. See [MCP Server](#mcp-server).

## Use It Well

1. **Start with a preset, not everything.** Pick the one that matches your work and add a category later.
2. **For a whole task, ask the hive.** Say "use sfp-manager for this task" at the start, and again when the work moves on, from building to testing or to shipping.
3. **For one skill, ask `sfp`.** "Use sfp to find a skill for adding rate limiting."
4. **Name the skill when you know it.** "Use the `impeccable` skill to critique this page."
5. **Tell it what helped.** The hive learns from the outcomes you record (see the questions below).
6. **Grow your install from use.** When you ask `sfp` for the same category three times, install it.

Prompts to try:

```text
Use sfp-manager for this task: harden this API before we ship it.
Use sfp to find a skill for stress-testing this form with long names and empty values.
Use sfp: I need a free API for currency exchange rates. Show auth and CORS for each.
Use the skill-creator skill to turn this checklist into a skill.
```

## How the Hive Works

A bee colony has no manager. The queen lays eggs; she does not hand out work. Yet thousands of bees split the jobs well, with rules that biologists have measured. The hive copies those rules to decide which skills your agent loads, and when.

| In a colony | In the hive | What it prevents |
|---|---|---|
| **Scouts** judge each nest site on their own | Five scouts judge each skill: the task's words, the project's files, the phase of work, the category, and the trail from the last skill used | One signal deciding alone |
| **Quorum**: the colony commits once enough scouts agree | A skill needs strong task words, or two scouts backing it | A rare word dragging in an unrelated skill |
| **Stop signals** between scouts for rival sites | Each chosen skill suppresses rivals in proportion to how alike they are | Two skills that do the same thing |
| **Response thresholds**: a bee takes a job when its need passes her threshold, and doing it lowers the need | Every job (plan, build, test, secure, ship) has a need; a skill takes the job it suits most, then that need drops | Five testing skills for one testing task |
| **Specialisation**: bees that do a job well take it up sooner | A skill you mark as helpful is chosen sooner | The same unhelpful skill coming back |
| **Pheromone trails** that evaporate | Recorded sequences of skills predict the next one, and fade over about a month | Stale habits steering forever |

```mermaid
flowchart LR
  T[task words] --> Q{quorum}
  P[project files] --> Q
  J[phase of work] --> Q
  C[category] --> Q
  H[trail from last skill] --> Q
  Q --> S[stop signals between rivals]
  S --> R[each skill takes the job it responds to most]
  R --> K[ordered stack: base, check, finish]
```

It runs inside the process that asks (the MCP server, or the skill's own script), so there is no middleman to wait on. Without Python, the skill gives the agent the same rules in plain words to apply itself. [docs/HIVE.md](docs/HIVE.md) has the algorithm, the biology, how it was built (the first versions were worse than the engine they replaced), and where it fails.

## Questions

**Does the hive slow my agent down?** No. A decision takes about @@HIVE_MS@@ ms and happens once per phase of work. It also loads fewer skills: @@BENCH_HIVE_SIZE@@ on average with no project.

**Does it always pick right?** No. The right skill was in the stack @@FRESH_HIVE@@ of the time on new tasks, and the misses are listed in [docs/HIVE.md](docs/HIVE.md#where-it-fails). When it misses, name the skill, or ask for a category.

**What does it record about me?** Only if you or your agent record usage: a skill name, a time and an outcome, in `~/.sfp/usage.jsonl` on your machine. Never prompts or code, and nothing is sent anywhere. Set `SFP_NO_USAGE_LOG=1` to turn it off, or delete the file to forget everything.

**Is it safe?** A skill is third-party instruction text that your agent will follow, so read a skill before you trust it, as you would a script. The installer writes only into skills folders and `~/.sfp`, and backs up an MCP config before changing it. The MCP server makes no network calls. Some skills do their own network work, such as Impeccable downloading its engine on first use.

**Why not install everything?** It works, and `--profile everything` does it. It puts about @@ALL_TOKENS@@ tokens of descriptions into every session and gives your agent @@TOTAL@@ to choose between.

**Which IDEs have you tested?** Claude Code end to end: plugin install from GitHub, the MCP connection, and a real session using the tools. For the other IDEs the installer was tested on fake home folders, and the folder paths follow each tool's documentation. The Windsurf and Copilot paths are unconfirmed.

**Can I keep my own skills?** Yes. A skill you made with the same name is left alone unless you pass `--force`.

**Does it work offline?** After installing, yes, for skills that do not need the network. The first install needs GitHub.

**Is a queen bee really in charge?** No, and that is the point. Work in a colony is divided by thresholds, recruitment, quorum and stop signals among equals. The hive copies those rules, not the myth.

**Can I go back to the previous engine?** Yes: `python3 mcp/sfp_hive.py recommend "..." --engine v1`.

**How do I remove it?** `./install.sh uninstall --tools cursor` for skills, `./install.sh mcp --remove` for the MCP server, and `/plugin uninstall <category>@sfp` in Claude Code.

## Pick a Preset

@@PRESET_TABLE@@

<details>
<summary>All @@NCATS@@ categories</summary>

@@CATEGORY_TABLE@@
</details>

## Supported IDEs

Claude Code, Codex, Cursor, Gemini CLI, Antigravity, GitHub Copilot, Windsurf, Kiro, OpenCode, Pi, Grok Build, Qoder, Trae, Rovo Dev, Mistral Vibe and Hermes. Name them with `--tools`:

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

## MCP Server

SFP also runs as an MCP server, so any MCP client can search and read all @@TOTAL@@ skills on demand, with nothing copied into a skills folder. It helps IDEs and agents that support MCP but not skills.

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- mcp
```

On Windows, in PowerShell:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1))) mcp
```

To pick IDEs, add `--tools cursor,claude`. To undo it, add `--remove`. By hand in Claude Code: `claude mcp add --scope user sfp -- python3 /path/to/SFP/mcp/sfp_mcp.py`. Any other MCP client: add a stdio server that runs `python3 /path/to/SFP/mcp/sfp_mcp.py`.

| Tool | What it does |
|---|---|
| `search_skills` | Finds skills by task or keyword, optionally within one category |
| `get_skill` | Returns a skill's full `SKILL.md` and the files it bundles |
| `read_skill_file` | Reads one bundled file, such as a reference doc or script |
| `list_categories` | Lists categories, skill counts and install presets |
| `find_api` | Searches the free API list by keyword, auth, CORS and HTTPS |
| `install_command` | Gives the command that installs a category or preset for good |
| `recommend_stack` | Runs the hive: the few skills a task needs, in order, for the project at `project_path` |
| `predict_next` | The skills most likely needed after one, by following pheromone trails |
| `record_usage` | Notes that a skill was used, and whether it helped, in `~/.sfp/usage.jsonl` |

Every skill is also a resource at `sfp://skill/{name}`, and two prompts, `use_skill` and `find_skill_for`, load a skill into a chat. The server needs only Python 3 and makes no network calls. It reads the project folder you pass to `recommend_stack`, and its one write is `record_usage`.

I tested it with Claude Code, including a real session that found and read a skill through the tools. The Cursor, Gemini CLI, Windsurf, Kiro and Codex settings follow each tool's documented format but were not run against those tools.

## Free APIs

The `public-apis` skill bundles a list of about 2,100 free APIs in 51 categories, plus a search script your agent can run directly:

```bash
python3 plugins/data-apis/skills/public-apis/scripts/find_api.py weather --auth none --cors yes
python3 plugins/data-apis/skills/public-apis/scripts/find_api.py --category Finance --limit 10
python3 plugins/data-apis/skills/public-apis/scripts/find_api.py --categories
```

Filters: `--auth none|apiKey|OAuth`, `--cors yes|no`, `--https yes|no` and `--json`.

## Full Integration: SFP, ECC and OmniRoute

SFP carries the **skills** of ECC and OmniRoute. ECC's agents, hooks and rules, and the OmniRoute gateway that routes your IDE to many model providers, need their own install. The short version, in order:

```bash
# 1. SFP skills and router
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh
# 2. SFP MCP server
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- mcp
# 3. ECC: agents, hooks, commands (Claude Code; Node.js 18+)
npx ecc-universal@2.2.3 setup
# 4. OmniRoute gateway, then point your IDE at http://localhost:20128/v1
npm install -g omniroute && omniroute
omniroute setup-claude        # or setup-codex, setup-cursor, setup-opencode ...
```

Use one ECC install method per IDE, and install only `sfp` plus non-ECC categories from SFP if you add the ECC plugin, so you do not get skills twice. The [full integration guide](docs/INTEGRATION.md) has every command per IDE, a verification table, updating and removal. I have not run ECC's or OmniRoute's installers myself: their commands come from each project's own documentation.

## Good to Know

- **career** is a launcher. The first time you use it, it clones the original career-ops project at a pinned commit into `~/.sfp/apps/career-ops` and applies a small patch (`templates/career/patches/data-root.patch`). Then run `npm install` there once. Your CV, tracker and reports live in `~/career-ops`, so updates never touch them.
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
- **Check your work:** `python3 -m unittest discover -s tests` runs the protocol, installer, search, hive and speed tests.

The README, banner, `plugins/`, `catalog.json`, `index.json` and `SKILLS.md` are generated. Edit `templates/README.md.tpl` and the JSON files, not the outputs.

```text
SFP/
  plugins/<category>/skills/<skill>/   the skills, one folder each (generated)
  mcp/sfp_mcp.py                       the MCP server
  mcp/sfp_hive.py                      the hive: the manager's engine
  mcp/sfp_stack.py, stack_recipes.json the v1 engine it builds on, and the recipes (permanent trails)
  scripts/install.py, sync.py          the installer, and the script that rebuilds everything
  templates/                           the sfp router, the manager skill, the career launcher, this README
  docs/                                HIVE.md, MANAGER.md, INTEGRATION.md
  vendor/                              snapshots of plugins that have no public repo
  archive/fork-patches/                commits the old forks held, kept as patches
  tests/                               protocol, installer, search, hive and speed tests
  sources.json, categories.json        where skills come from and how they are sorted
```

## Sources and Licenses

SFP's own code (the installer, sync script, MCP server, hive, router and manager skills, tests and README) is under the [MIT License](LICENSE). That covers only what SFP wrote. Each skill keeps the license of the project it came from. [NOTICE.md](NOTICE.md) lists every source, and each category folder holds copies of its licenses in `plugins/<category>/LICENSES/`. The full skill list is in [SKILLS.md](SKILLS.md).

<details>
<summary>Where every source landed (@@SOURCES@@ sources)</summary>

Every skill in these repos is in SFP, except test fixtures and translated example copies. Repos with no skill of their own got one written for them. Plugins with no public repo are kept as snapshots in `vendor/`.

SFP reads the original repos directly, and `sources.lock.json` records the exact commit of each one that was integrated. It does not depend on any fork. The extra commits the forks held are saved as patches in [archive/fork-patches](archive/fork-patches).

| Source | Where it is in SFP |
|---|---|
| pbakaus/impeccable | `frontend`: Impeccable, 24 design commands |
| Imaidazo/taste-skill-plugin | `frontend`: the Taste skills |
| emilkowalski/skills | `frontend`: Emil Kowalski's skills |
| vercel-labs/web-interface-guidelines | `frontend`: a UI review checklist |
| design-skills | `frontend`: 10 UX design skills |
| bergside/awesome-design-skills | `design-styles` |
| usestrix/strix | `security` |
| anthropics/claude-plugins-official | `agent-dev` and others: every skill it ships. Its other plugins point to third-party repos |
| affaan-m/everything-claude-code | spread across `agents`, `agent-dev`, `backend`, `frontend`, `testing-quality` and more |
| diegosouzapw/OmniRoute | `ai-gateway`, plus 6 maintenance skills in `devops` |
| thedotmack/claude-mem | `memory`, and the optional `session-memory` plugin |
| Panniantong/Agent-Reach | `data-apis` |
| public-apis/public-apis | `data-apis`: a searchable skill over about 2,100 free APIs |
| tashfeenahmed/freellmapi | `data-apis`: a skill with the project's docs |
| harry0703/MoneyPrinterTurbo | `content-media` |
| marketing-psychology | `content-media`: 5 persuasion and behavior skills |
| Anthropic example skills | 8 Apache-2.0 skills: algorithmic art, brand guidelines, canvas design, internal comms, MCP builder, Slack GIF creator, theme factory, web artifacts builder |
| teach-me | `research-docs` |
| task-observer, headroom | `agent-dev` |
| cowork-plugin-management | `agent-dev` |
| gia-chief-of-staff | `business-ops` |
| career-ops-hq/career-ops | `career`: a launcher that sets up the project at a pinned commit with SFP's patch |

**Left out on purpose:** anything whose license does not allow republishing. That covers Greenhouse's customer-only plugin, Anthropic's docx, pdf, pptx, xlsx and browser skills (all rights reserved), and the noncommercial-only `claude-mem-cowork` plugin.
</details>
