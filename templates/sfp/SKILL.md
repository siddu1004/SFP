---
name: sfp
description: SFP (Skills for Productivity) is a library of about 520 agent skills sorted into categories - frontend, backend, mobile, languages, testing, devops, security, agents, agent-dev (skills, plugins, hooks, MCP), AI/ML, AI gateway, data APIs, content, business, industry, networking, research, web3, engineering, memory. Use it first whenever a task might have a matching skill - building UI, APIs or apps, reviewing or securing code, designing agents, plugins or MCP servers, finding a free API or data source, writing or video work - or when the user asks "is there a skill for...", "what can SFP do", or which skill to use.
---

# SFP: pick the right skill

Skills sit in categories. Find the one that fits, read it, and follow it.

For a task with several steps (build, then test, then ship), use the `sfp-hive` skill first: it picks the few skills that fit the task and this project, in order. Use the steps below for a single skill.

## 1. Find the skill

Search `reference/index.md` in this skill's folder. It has one line per skill, grouped by category. Search it for words from the task rather than reading all of it:

- by category: find the `## <category>` heading and read until the next one
- by keyword: search the file, case-insensitive, and try synonyms ("auth", "login", "oauth")

| If the task is about | Category |
|---|---|
| UI, components, motion, accessibility, React, Vue, Next.js | `frontend`, and `design-styles` for a named look |
| APIs, databases, Django, FastAPI, Spring, Laravel, NestJS, Rails, Postgres | `backend` |
| Android, iOS, Flutter, React Native, Swift, Kotlin | `mobile` |
| Go, Rust, Python, C++, C#, Java, Perl idioms | `languages` |
| tests, TDD, E2E, code review, verification | `testing-quality` |
| Docker, Kubernetes, deploys, git, GitHub | `devops` |
| pentesting, vulnerabilities, secure coding | `security` |
| running agents, loops, orchestration, planning, feature pipelines | `agents` |
| building skills, plugins, hooks, MCP servers, agent memory, token budgets | `agent-dev` |
| LLM pipelines, prompts, evals, RAG, PyTorch, ML | `ai-ml` |
| an OmniRoute AI gateway | `ai-gateway` |
| a free API, a data source, internet search or scraping | `data-apis` |
| writing, SEO, video, slides, social posts | `content-media` |
| billing, finance, investors, leads, contracts, email, tickets | `business-ops` |
| healthcare, logistics, customs, inventory, energy | `industry` |
| networks, homelab, Cisco, BGP, VLANs | `networking` |
| research, papers, docs, ADRs, onboarding to a codebase | `research-docs` |
| DeFi, EVM, prediction markets | `web3` |
| architecture, standards, performance, refactoring | `engineering` |
| math proofs, Blender, M5Stack hardware | `science-hardware` |
| job search, CVs, applications | `career` |
| claude-mem, session memory, handoffs, timelines | `memory` |

## 2. Use it

- If the skill is installed, it shows in your skill list: invoke it by name.
- If it is not installed, read its file directly from the SFP checkout and follow it as if it were loaded: `<SFP>/plugins/<category>/skills/<name>/SKILL.md`. Find `<SFP>` in this order:
  1. the folder written in `~/.sfp/root` (the installer writes it),
  2. `~/.claude/plugins/marketplaces/sfp`,
  3. the current project, if it is the SFP repo.
  Skill files point to their own `reference/` and `scripts/` folders by relative path; resolve those against the skill's folder.
- If you cannot find a checkout, tell the user the skill exists and how to get it: `./install.sh install --categories <category>` from the SFP repo, or `/plugin install <category>@sfp` in Claude Code.

## 3. Free APIs and data

For "is there an API for X", "I need data about Y" or "find me a free API", use the `public-apis` skill (category `data-apis`). It searches about 2,100 free APIs and returns links with auth, HTTPS and CORS details. Do not answer from memory when it is available.

## Rules

- Prefer one specific skill over several vague ones. Most tasks need one or two.
- Load a skill only when the task calls for it. Do not read skills "just in case".
- When two skills overlap (for example `frontend` and `design-styles`), the narrower one wins: use the named style when the user names a style, the general one otherwise.
- If no skill fits, say so and carry on with the task normally.
