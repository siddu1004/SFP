---
name: codebase-memory-mcp
description: "Connect persistent local code intelligence and architectural dependency graphs using Codebase Memory MCP. Use when exploring complex codebases, querying architectural relationships, or maintaining cross-session code context."
---

# Codebase Memory MCP

Persistent local code graph and architectural memory server via Model Context Protocol (`DeusData/codebase-memory-mcp`). Connects code, documentation, schemas, and dependencies in a local queryable graph.

## Use This Skill When

- Analyzing large, unfamiliar codebases with cross-cutting dependencies.
- Querying call graphs, type inheritance, and architectural relationships across modules.
- Preserving architectural insights and refactoring maps across agent restarts.

## Tools & Capabilities

- `get_architecture_overview`: Summarize top-level subsystems and data flows.
- `find_dependents`: List all modules or files impacted by changes to a target symbol.
- `search_code_memory`: Semantic and symbol query across indexed project graph.

## Sources

- [Codebase Memory MCP GitHub Repository](https://github.com/DeusData/codebase-memory-mcp)
