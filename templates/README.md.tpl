<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img src="assets/banner-light.svg" alt="SFP: Skills for Productivity" width="100%">
  </picture>
</h1>

<p align="center">
  <b>Give your AI coding agent the right skills for the job, not all of them.</b><br>
  @@TOTAL@@ skills, sorted by what you build. A hive picks the few each task needs, for the project in front of it, and learns from your feedback.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-@@SEL_VERSION@@-0f766e?style=flat-square&labelColor=3b4350" alt="Version @@SEL_VERSION@@">
  <img src="https://img.shields.io/badge/skills-@@TOTAL@@-0f766e?style=flat-square&labelColor=3b4350" alt="@@TOTAL@@ skills">
  <img src="https://img.shields.io/badge/installs_into-16_IDEs-0f766e?style=flat-square&labelColor=3b4350" alt="Installs into 16 IDEs and CLIs">
  <img src="https://img.shields.io/badge/tested_end_to_end-Claude_Code-0f766e?style=flat-square&labelColor=3b4350" alt="Tested end to end in Claude Code">
  <img src="https://img.shields.io/badge/needs-Python_3-0f766e?style=flat-square&labelColor=3b4350" alt="Needs Python 3">
  <img src="https://img.shields.io/badge/license-MIT-0f766e?style=flat-square&labelColor=3b4350" alt="MIT license">
</p>

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/results-numbers-dark.svg">
  <img src="assets/results-numbers-light.svg" alt="86% right skill on unseen tasks (plain search 9%); 5 of 6 pages shipped with SFP against 4 of 6 without skills; @@TOTAL@@ skills" width="100%">
</picture>
</p>

<p align="center">
  <a href="#try-it-in-60-seconds"><b>Try in 60s</b></a> &middot;
  <a href="#the-problem"><b>Why We Built It</b></a> &middot;
  <a href="#what-sfp-does"><b>What It Does</b></a> &middot;
  <a href="#see-it-choose"><b>Live Selection</b></a> &middot;
  <a href="#platform-capabilities"><b>Platform Capabilities</b></a> &middot;
  <a href="#why-choose-sfp"><b>Benchmark Results</b></a> &middot;
  <a href="#the-proof"><b>The Proof</b></a> &middot;
  <a href="#install"><b>Install</b></a>
</p>

## Try It in 60 Seconds

```bash
# Cross-platform (Windows, macOS, Linux via npm / npx):
npx sfp-hive install

# Or via curl (macOS and Linux):
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh

# Or via PowerShell (Windows):
irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1 | iex
```

Installs the starter preset into every IDE found on your machine. Restart your IDE, then prompt your agent:

> Use sfp-hive for this task: add tests for the checkout form.

The agent selects the exact skills matching your stack, explains why, and executes in sequence. When finished, feedback (`helped`, `unhelpful`) teaches the hive to choose better next time.

Uninstall cleanly anytime: `~/.sfp/SFP/install.sh uninstall` (or `.\install.ps1 uninstall` on Windows).

---

## The Problem

High-quality agent skills exist, but using them today forces a painful tradeoff:

- **The 58,000-Token Tax**: Agents read every installed skill description at session start. For @@TOTAL@@ skills, that consumes **@@ALL_TOKENS@@ tokens** (@@ALL_PERCENT@@% of a 200k context window) before you type a single prompt.
- **Dumb Search Fails Across Stacks**: Asking for "write tests" requires completely different skills in Next.js (`react-testing`), Django (`django-tdd`), or Rust (`rust-testing`). Keyword search cannot see your project structure.
- **Fragmented Ecosystem**: 52 upstream repositories use different file layouts, paths, and metadata formats across 16 IDEs.
- **Static Guesswork**: Without feedback and reinforcement learning, agent tooling repeats the same bad selections indefinitely.

---

## What SFP Does

SFP brings biological collective intelligence to agent skill orchestration:

| Capability | Mechanism | Impact |
|---|---|---|
| **Curate & Unify** | @@SOURCES@@ repositories merged into @@NCATS@@ categories, organized by role presets | Complete coverage across frontend, backend, security, DevOps, and AI |
| **Dynamic Hive Selection** | 5 scout signals (task words, project files, work phase, category, history) reach quorum | **@@SFP_TOKENS@@ tokens** carried instead of @@ALL_TOKENS@@: **@@RATIO@@x reduction** |
| **LinUCB Bandit & RL** | Contextual bandit exploration plus implicit reward harvesting from test runs and git commits | **@@LC_FIXED@@ of reported mistakes fixed** on retry |
| **Universal Delivery** | Native folder injection for 16 IDEs + zero-install MCP server + VS Code / Antigravity extension | Install once, run anywhere |
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/hive-architecture-dark.svg">
    <img src="assets/hive-architecture-light.svg" alt="SFP Hive Decision Engine Architecture" width="100%">
  </picture>
</p>

### How the Hive Operates

1. **Scouts (Five Signals)**: Candidate skills are scored by prompt intent, project manifests (`package.json`, `Cargo.toml`, etc.), current phase (plan, build, test, ship), category alignment, and Markov sequence history.
2. **Quorum Consensus**: A skill only enters the stack if backed by multiple signals or high task confidence, with strict filtering against foreign technologies.
3. **Cross-Inhibition (Stop Signals)**: Once a testing or design skill is chosen, overlapping alternatives are suppressed to prevent duplicate guidance.
4. **Division of Labor**: Roles (base, check, finish) are filled according to task needs.
5. **Continuous Learning**: A regularized model updates from explicit verdicts and automatic rewards (+1.0 for passing test suites, +0.5 for git commits, -0.6 for test failures).

---

## See It Choose

The exact same prompt &mdash; *"write tests for the orders"* &mdash; executed in five distinct projects. Output is generated live by the hive:

@@SAME_WORDS_TABLE@@

Notice that plain keyword search yields identical, generic results everywhere. The hive inspects project manifests so zero stacks receive tools for the wrong technology.

---

## Platform Capabilities

SFP supports 16 IDEs and provides three flexible delivery modes:

<p align="center">
  <img src="assets/extension-preview.png" alt="SFP Hive Studio: Visual Bundle Inspector, Keyword Attribution, and Model Router" width="100%">
</p>

### 1. The SFP Hive Extension (Antigravity & VS Code)
- **Automatic Skills**: Automatically syncs active skills to `.agents/rules/sfp-active-skills.md`. The agent consumes targeted instructions on every turn without copy-pasting.
- **Bundle Inspector**: Visualizes multi-skill recipes, match confidence percentages, and the exact task keyword chips driving the choice.
- **Local Model Router**: Manages local backends (Ollama, LM Studio, llama.cpp, vLLM) with automatic failover and zero telemetry.

### 2. Zero-Footprint MCP Server
- Serves all @@TOTAL@@ skills dynamically via standard JSON-RPC over stdio.
- Tools supported: `search_skills`, `get_skill`, `select_skills`, `give_feedback`, `predict_next`, and `find_api`.
- Zero context bloat: skills are loaded on demand only when invoked.

### 3. Native IDE Folder Sync
- One command installs targeted presets into native skill directories across 16 IDEs: Claude Code, Cursor, Codex, Gemini CLI, Antigravity, GitHub Copilot, Windsurf, Kiro, OpenCode, Trae, and more.

---

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

---

## Why Choose SFP

Rigorous benchmarks against baselines and plain keyword search:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/results-rounds-dark.svg">
  <img src="assets/results-rounds-light.svg" alt="Review rounds until a reviewer would ship the page: 2.8 with SFP, 3.7 with no skills" width="100%">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/results-accuracy-dark.svg">
  <img src="assets/results-accuracy-light.svg" alt="Right skill on held-out tasks: SFP hive 86%, earlier engine 64%, plain search 9%" width="100%">
</picture>

### Summary of Verified Results

1. **One Full Round Faster to Ship**: In blind multi-round design evaluations scored by an independent judge, agents guided by SFP shipped ready pages in **2.8 rounds** versus **3.7 rounds** unassisted.
2. **86% Selection Accuracy**: On 22 held-out tasks across 8 unseen projects, SFP Hive achieved **86% precision** compared to **9%** for plain keyword search.
3. **100% Success on Unfamiliar Tools**: When challenged with novel tools (FreeLLMAPI), unguided agents met 0 of 7 automated validation checks; with SFP skills, agents passed all 7 checks cleanly ([docs/EFFECT.md](docs/EFFECT.md)).
4. **Sub-6ms Speed**: Decisions execute locally in under 6 milliseconds, with zero network lag and total privacy.

---

## The Proof

Figures below are computed directly from this repository during the build. Reproduce with `python3 mcp/sfp_hive.py evaluate` and `python3 mcp/sfp_hive.py learning-curve`.

| Task set | Hive @@SEL_VERSION@@ | Earlier engine | Plain search |
|---|---:|---:|---:|
| 22 held-out tasks in 8 new projects, written first and scored once | **@@FRESH_SEL@@** | @@FRESH_V1@@ | @@FRESH_SEARCH@@ |
| 24 tasks in 10 sample projects | @@PROJ_SEL@@ | @@PROJ_V1@@ | @@PROJ_SEARCH@@ |
| 91 tasks with no project | @@BENCH_SEL@@ | @@BENCH_V1@@ | @@BENCH_SEARCH@@ |
| Stacks with a skill for the wrong technology, all sets | @@WRONG_SEL@@ | @@WRONG_V1@@ | @@WRONG_SEARCH@@ |

**What does it cost your agent?**

@@COST_TABLE@@

**How fast is it?**

Decisions take about @@SEL_MS@@ ms inside the host process. Search takes about 0.1 ms. MCP queries execute in 3 to 5 ms once the project tree is indexed ([docs/HIVE.md](docs/HIVE.md#speed)).

> **What has not been measured.** Whether the chosen skills make your agent's finished work better across every domain. Learning is measured on a simulated user, not on real long-run use. Tasks and ground truths were written and validated by human evaluators. Token counts are estimated at 4 characters per token.

---

## Install

Quick install options for all platforms:

<details open>
<summary><b>1. npm / npx (Cross-Platform)</b></summary>

```bash
npx sfp-hive install
```
</details>

<details>
<summary><b>2. macOS and Linux (curl)</b></summary>

```bash
# Starter preset into all detected IDEs:
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh

# Target a specific IDE and preset:
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --tools cursor --profile frontend-dev
```
</details>

<details>
<summary><b>3. Windows (PowerShell)</b></summary>

```powershell
# Starter preset:
irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1 | iex

# Custom IDE & profile:
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1))) --tools cursor --profile frontend-dev
```
</details>

<details>
<summary><b>4. Claude Code Plugin</b></summary>

```text
/plugin marketplace add siddu1004/SFP
/plugin install sfp@sfp
/plugin install frontend@sfp
```
</details>

<details>
<summary><b>5. Zero-Install MCP Server</b></summary>

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- mcp
```

Registers `sfp` with all detected IDEs, granting on-demand access to all @@TOTAL@@ skills without adding files to disk.
</details>

<details>
<summary><b>6. VS Code / Antigravity Hive Extension</b></summary>

```bash
python3 extensions/antigravity-hive/install.py
```

Builds and installs the native `.vsix` extension with bundle visualization and auto-skills tracking.
</details>

---

## Supported IDEs

Claude Code, Codex, Cursor, Gemini CLI, Antigravity, GitHub Copilot, VS Code, Windsurf, Kiro, OpenCode, Pi, Grok Build, Qoder, Trae, Rovo Dev, Mistral Vibe, and Hermes.

Install into specific tools:
```bash
./install.sh --tools claude,cursor,antigravity,codex
```

See [docs/INSTALL.md](docs/INSTALL.md) for full setup instructions, IDE paths, and verification checklists.

---

## Sources and Licenses

SFP's selection engine, installer, and MCP server are licensed under the [MIT License](LICENSE). Each skill preserves the license and copyright of its original upstream author. Detailed attributions are cataloged in [NOTICE.md](NOTICE.md) and [SKILLS.md](SKILLS.md).
