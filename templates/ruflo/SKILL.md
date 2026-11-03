---
name: ruflo
description: "Deploy and coordinate multi-agent swarms using Ruflo for efficient task execution and collaboration. Use when deploying and coordinating swarms of agents with ruflo."
---

> Written for SFP in its own words from the project at https://github.com/ruvnet/ruflo (upstream license: MIT).

# Deploying Multi-Agent Swarms with Ruflo

## Use this skill when
- You need to manage multiple AI agents working together on complex tasks.
- You want to leverage the coordination features of Ruflo for better performance and scalability.

## What it is
Ruflo is a meta-harness that enables the deployment and management of multi-agent swarms. It provides tools for agent coordination, memory retention, and secure communication across different machines.

## Steps
1. **Initialize Ruflo in your project:**
   ```bash
   npx ruflo@latest init wizard
   ```
2. **Install necessary plugins:**
   - Core tools:
     ```text
     /plugin marketplace add ruvnet/ruflo
     /plugin install ruflo-core@ruflo
     /plugin install ruflo-console@ruflo
     /plugin install ruflo-mods@ruflo
     /reload-plugins
     ```
   - Ruflo in Codex or another MCP enabled tool:
     ```bash
     npx -y ruflo@latest mcp start
     ```
3. **Configure the terminal UI (optional):**
   ```bash
   npx ruflo tui
   ```
4. **Set up ruOS Desktop for advanced features:**
   ```text
   https://ruos.cognitum.one/mcp
   ```

## Checks
- Ensure all plugins are installed and running.
- Verify that the terminal UI displays the expected information (Overview, Cost, Swarm, Events, Missions).
- Confirm that agents are self-organizing into swarms as intended.

## Pitfalls
- **Version Compatibility:** Make sure you have the required version of Claude Code or Codex.
- **Security Risks:** Review and understand the permissions granted to mods before installing them.
- **Resource Management:** Monitor resource usage to prevent overloading your system with too many agents.
