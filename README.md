# SFP: Skills for Productivity

528 agent skills from 15 repos, sorted by what you build: frontend, backend, mobile, security, agent-driven work, AI, data APIs and more. One `sfp` router skill knows all of them and sends the agent to the right one.

It works in Claude Code and in every other agent IDE or CLI that reads skills (`SKILL.md` folders): Codex, Cursor, Gemini CLI, Antigravity, GitHub Copilot, Windsurf, Kiro, OpenCode, Pi, Grok Build, Qoder, Trae, Rovo Dev, Mistral Vibe and Hermes.

The full list is in [SKILLS.md](SKILLS.md).

## Install codes

Pick the line for your setup. All of them need `git` and, outside Claude Code's plugin route, Python 3.

**Claude Code** (inside Claude Code):

```
/plugin marketplace add siddu1004/SFP
/plugin install sfp@sfp
/plugin install frontend@sfp
/plugin install backend@sfp
```

Swap `frontend` and `backend` for any category below. Install one at a time, or all of them.

**macOS and Linux, any IDE** (installs the starter set into every tool it finds):

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh
```

**Windows PowerShell, any IDE:**

```powershell
irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1 | iex
```

**Everything, into every IDE found:**

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --profile everything
```

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1))) --profile everything
```

**One IDE, one preset** (`--tools` takes `claude`, `codex`, `cursor`, `gemini`, `antigravity`, `copilot`, `windsurf`, `kiro`, `opencode`, `pi`, `grok`, `qoder`, `trae`, `rovodev`, `vibe`, `hermes`):

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --tools cursor --profile frontend-dev
```

**From a clone** (the same installer; you can read it first):

```bash
git clone https://github.com/siddu1004/SFP.git && cd SFP
./install.sh list                                      # categories, profiles, which tools were found
./install.sh --profile backend-dev                     # a preset
./install.sh --categories security,devops,memory       # exact categories
./install.sh --tools cursor,codex                      # only these tools
./install.sh --project .                               # into this project's .cursor/, .agents/ ... folders
./install.sh --link                                    # symlink so `git pull` updates skills in place (macOS / Linux)
./install.sh uninstall --tools cursor
```

On Windows use `.\install.ps1` in place of `./install.sh`.

**Any agent, no script:** paste this to it.

> Clone https://github.com/siddu1004/SFP, run its `install.sh` (or `install.ps1` on Windows) with `--tools <this tool>`, then restart me so the skills load.

Profiles: `starter` (the default), `frontend-dev`, `backend-dev`, `mobile-dev`, `agent-builder`, `everything`. Edit them in `sources.json`. Re-run the same line any time to update.

The installer only replaces or removes folders it created itself. A skill with the same name that you made yourself is left alone unless you pass `--force`.

## Is everything in here?

Every skill in the repos below is in SFP, except the maintainers' own test fixtures and translated example copies. Repos that have no skill of their own got one written for them.

| Repo | Where it is in SFP |
|---|---|
| impeccable | `frontend` (Impeccable, 24 design commands) |
| taste-skill-for-claude-and-antigravity | `frontend` (8 taste skills) |
| skills-claude-antigravity | `frontend` (Emil Kowalski's 15 skills) |
| awesome-design-skills | `design-styles` (67 styles) |
| strix | `security` (9 skills) |
| claude-plugins-official | `agent-dev` and others (every skill it ships; its other ~290 entries are pointers to third-party repos) |
| ECC | spread across `agents`, `agent-dev`, `backend`, `frontend`, `testing-quality` and more (313 skills) |
| OmniRoute | `ai-gateway` (45) and `devops` (6 maintenance skills) |
| claude-mem | `memory` (31 skills) and the optional `session-memory` plugin |
| Agent-Reach | `data-apis` |
| public-apis | `data-apis`, as a searchable skill over about 2,100 free APIs |
| freellmapi | `data-apis`, a skill with the project's docs bundled |
| MoneyPrinterTurbo | `content-media` |
| career-ops | `career` (installed from its own repo) |
| sai_ai_my_own_jarvis | `sai` (installed from its private repo, so only accounts with access get it) |

## How it is organised

Skills live in categories under `plugins/<category>/skills/<skill>/`. Each category is also a Claude Code plugin.

| Category | Skills | What's in it |
|---|---|---|
| `sfp` | 1 | The router: finds the right skill for any task, installed or not |
| `frontend` | 49 | UI design, components, motion, accessibility, React, Vue, Next.js, Angular, Vite. Includes Impeccable, the Taste skills and Emil Kowalski's animation skills |
| `design-styles` | 67 | Named visual styles: brutalism, glassmorphism, editorial, retro, shadcn and more |
| `backend` | 27 | Django, FastAPI, Spring Boot, Laravel, NestJS, Rails, Postgres, MySQL, Redis, Prisma, API design |
| `mobile` | 13 | Android, iOS, Flutter, React Native, Kotlin Multiplatform, Swift |
| `languages` | 8 | Go, Rust, Python, C++, Java, Kotlin, Perl idioms and standards |
| `testing-quality` | 32 | TDD, end-to-end tests, verification loops, code review, regression, quality gates |
| `devops` | 15 | Docker, Kubernetes, deployment, git and GitHub workflows, terminals, green-PR and merge automation |
| `security` | 21 | Strix autonomous pentesting, OWASP testing, secure coding per framework, agent hardening |
| `agents` | 33 | Agent-driven work: autonomous loops, orchestration, councils, dev teams, feature pipelines |
| `agent-dev` | 57 | Building for agents: skills, plugins, hooks, MCP servers, harnesses, token budgets |
| `memory` | 31 | claude-mem's skills: search past work, timelines, handoffs, planning with persistent memory |
| `ai-ml` | 10 | LLM pipelines, prompts, evals, PyTorch, ML engineering, recommenders |
| `ai-gateway` | 45 | Driving an OmniRoute AI gateway: routing, providers, budgets, caching, MCP, A2A |
| `data-apis` | 7 | A searchable list of about 2,100 free APIs, FreeLLMAPI, internet reach across 16 platforms, search, scraping |
| `content-media` | 17 | Writing, marketing, SEO, video, slides, social posting |
| `business-ops` | 25 | Billing, finance, investors, market research, leads, contracts, email, tickets |
| `industry` | 13 | Healthcare, logistics, customs, inventory, production, energy |
| `networking` | 10 | Cisco IOS, BGP, VLANs, WireGuard, Pi-hole, homelab |
| `research-docs` | 17 | Deep research, scientific databases, literature review, docs, ADRs |
| `web3` | 9 | DeFi, EVM, prediction markets, trading-agent security |
| `engineering` | 15 | Architecture, standards, error handling, performance, benchmarks |
| `science-hardware` | 6 | Math proofs, Blender, M5Stack and Cardputer |
| `career` | plugin | AI job search: evaluate offers, tailor CVs, scan portals, track applications (career-ops) |
| `sai` | plugin | Sai, your own voice assistant (private repo) |
| `session-memory` | plugin | claude-mem's full plugin with hooks and worker. Claude Code only |

`ecc-full` and `omniroute-full` are optional Claude Code plugins that add the hooks, agents and commands of Everything Claude Code and OmniRoute. Their skills are already spread across the categories above, so install either the full plugin or the categories.

## The `sfp` skill

Agents read the description of every installed skill at the start of each session, and 528 descriptions is too much to carry. So you do not have to install everything. Install the `sfp` skill plus the categories you use daily. For the rest, `sfp` has an index of every skill, finds the right one by task, and reads it straight from this checkout on demand. The installer records the checkout path in `~/.sfp/root` for that.

## Free APIs for any need

The `public-apis` skill (category `data-apis`) holds a bundled list of about 2,100 free APIs in 51 categories and a search script, so an agent can query it directly:

```bash
python3 plugins/data-apis/skills/public-apis/scripts/find_api.py weather --auth none --cors yes
python3 plugins/data-apis/skills/public-apis/scripts/find_api.py --category Finance --limit 10
python3 plugins/data-apis/skills/public-apis/scripts/find_api.py --categories
```

Filters: `--auth none|apiKey|OAuth`, `--cors yes|no`, `--https yes|no`, `--json`. It needs only Python 3.

## Claude Code notes

If the `claude` command is on your PATH, the installer adds this repo as a marketplace and installs each category as a plugin. Plugins update with `/plugin update`. Pass `--copy` to the installer to copy plain skill folders into `~/.claude/skills` instead.

### Where each tool's skills go

| Tool | Your home folder | A project (`--project`) |
|---|---|---|
| Claude Code | `~/.claude/skills` | `.claude/skills` |
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

A tool counts as found when its home folder exists (for example `~/.cursor`). Name tools with `--tools` to install into one that isn't found yet. The Windsurf and Copilot paths are my best reading of their docs; if one is wrong for your version, fix it in the `TOOLS` table in `scripts/install.py`.

### Skills with extra needs

- **career** runs from its own checkout, cloned into `~/.sfp/apps/career-ops`. Set it up once there with `npm install`. Your CV, tracker and reports are kept separately in `~/career-ops`.
- **sai** is cloned from the private repo into `~/.sfp/apps/sai`, using your git credentials. If the clone is refused, the installer skips it and carries on. Set it up once there with `pip install -r requirements.txt` inside a virtual environment.
- **session-memory** needs Claude Code's hooks and a background worker, so other tools skip it. The `memory` skills work without it but are written for claude-mem, so most want it installed.
- **ai-gateway** skills drive an OmniRoute server, and **security** skills drive the Strix CLI. Each skill explains how to install what it needs.
- **Impeccable** (in `frontend`) downloads its engine binary on first use.

## Updating

Re-run your install line. To pull the latest versions from the source repos into SFP itself, run `python3 scripts/sync.py` and commit the result. It shallow-clones each repo in `sources.json` into `.cache/`. Use `--src-dir DIR` to read checkouts you already have, and `--report` to see what each category got.

## Adding a repo or moving a skill

- **New repo:** add an entry to `sources.json` (`repo`, `license`, `default` category, `skills` glob paths to folders that contain a `SKILL.md`), then run `python3 scripts/sync.py`.
- **Wrong category:** add the skill's name to `names` in `categories.json`, or adjust a regex under `patterns`, then sync. Exact names win over patterns, and sources marked `"fixed": true` keep their `default` unless a name is listed.
- **New category:** add it under `categories` in `categories.json`. Names must not start with `claude-` or `anthropic-`; Claude Code reserves them.
- A skill whose name is already taken by a different skill gets a prefix (`collision_prefix` in its source). `name_prefix` prefixes every skill from a source.

Do not edit `plugins/`, `catalog.json`, `SKILLS.md` or `.claude-plugin/marketplace.json` by hand; the sync regenerates them.

## Sources and licenses

Each category keeps a copy of its source licenses in `plugins/<category>/LICENSES/`, and [NOTICE.md](NOTICE.md) lists every source. Each skill keeps its original license.
