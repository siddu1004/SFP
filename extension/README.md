# SFP Hive Live Skill Monitor & Agentic Extension

A live skill monitor and prompt engineering sidebar extension for Antigravity IDE and VS Code-compatible editors.

## Features

- **Real-Time Dynamic Prompt Analysis**:
  As you type or modify your prompt, the SFP Hive engine analyzes task intent, project context, and phase of work in real time.
- **Dynamic Skill Delta Tracking**:
  Clearly displays which skills are added (`+ green`) or subtracted (`- red`) as the prompt wording shifts.
- **Three-Tier Layer Breakdown**:
  - **Base Layer (Grounding)**: Project conventions, patterns, and foundational skills.
  - **Check Layer (Safety & Standards)**: Verification, TDD, security, and edge-case guards.
  - **Finish Layer (Review & Polish)**: Polish, optimization, and documentation polishers.
- **Interactive Stack Customizer**:
  Toggle individual skills on/off with checkboxes to customize your agent prompt stack.
- **Token Context Budget Gauge**:
  Visual bar tracking estimated token overhead against the 12,000 token context budget.
- **Feedback & Learning Integration**:
  1-click 👍 (Helped) or 👎 (Unhelpful) feedback buttons record decisions directly to `~/.sfp/feedback.jsonl` to train the associative model.
- **⚡ Retrain Model Button**:
  Retrains the Hive's Bayesian associative weights from benchmarks and user feedback right from the UI.
- **📋 Copy Stack**:
  1-click button to copy formatted skill references ready to inject into your agent prompt.

## Architecture

- **Extension Host**: Zero external npm dependencies. Communicates with `mcp/sfp_hive.py` via native child processes.
- **Webview UI**: Clean Antigravity dark theme with live IPC message passing.
- **Direct Catalog Integration**: Reads all 814 skills and categories from `catalog.json`.
