---
name: gitnexus
description: "Index codebase structure and query cross-repository knowledge graphs using GitNexus AST analysis. Use when navigating unfamiliar codebases, tracing cross-file dependencies, or mapping symbol references across repos."
---

> **This skill needs GitNexus, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.

# GitNexus Code Knowledge Graph

Multi-repository knowledge graph and AST analysis tool designed for AI coding agents. GitNexus parses source files into symbol graphs, enabling agents to query call graphs, symbol references, and cross-package dependencies without full-text grep scans.

## Use this skill when
- Onboarding onto complex multi-package or monorepo architectures.
- Tracing function call chains, inheritance hierarchies, and import dependencies.
- Analyzing the blast radius of structural API refactors across multiple files.

## Steps
1. **Run repository analysis**:
   Analyze the codebase and construct the symbol graph:
   ```bash
   npx gitnexus analyze
   ```
2. **Query symbol relationships**:
   Inspect callers, callees, and imported definitions:
   ```bash
   npx gitnexus query "symbols/AuthService" --type callers
   ```
3. **Trace cross-file dependencies**:
   Generate an impact report before modifying core shared interfaces:
   ```bash
   npx gitnexus impact --symbol "renderComponent"
   ```
4. **Export dependency graphs**:
   Export graph data in JSON format for agent consumption and automated review.

## Checks
- Check that the analysis run generated `.gitnexus/graph.json` without parse failures.
- Verify that tracked symbol paths correspond to active files in the workspace.

## Pitfalls
- Monorepos with dynamic imports may require configuring module aliases in `gitnexus.config.json`.
- Exclude `node_modules`, `dist`, and build output directories to maintain fast query performance.

## Sources
- [GitNexus GitHub Repository](https://github.com/abhigyanpatwari/GitNexus)
