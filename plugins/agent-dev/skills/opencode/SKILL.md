---
name: opencode
description: "Automate coding workflows using OpenCode CLI (opencode) and terminal subagents. Use when orchestrating background coding tasks, running automated pull request triage, or integrating multi-model coding workflows."
---

> **This skill needs OpenCode, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.

# OpenCode CLI

Orchestrate automated coding tasks, multi-model execution, and git triage using OpenCode (`anomalyco/opencode`). OpenCode provides an agentic coding environment with dual operational modes: full-access `build` and read-only `plan`.

## Use This Skill When

- Running background coding subagents from the terminal.
- Triage and automate PR review, issue diagnosis, or test-driven implementation loops.
- Switching dynamically between local models and frontier LLMs for code synthesis.

## Quick Start & Commands

```bash
# Install globally
npm i -g @opencode/cli@latest

# Launch terminal interface in current workspace
opencode

# Execute a one-shot planned refactor
opencode run --mode plan "Analyze authentication flow in src/auth for CSRF vulnerabilities"
```

## Modes & Safety

- **Plan Mode**: Read-only codebase indexing, AST inspection, and proposal generation without modifying disk.
- **Build Mode**: Full write access to apply surgical edits, run test suites, and commit changes.

## Sources

- [OpenCode Official Website](https://opencode.ai/)
- [OpenCode GitHub Repository](https://github.com/anomalyco/opencode)
