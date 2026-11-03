---
name: graft
description: "Compile and execute declarative multi-agent pipelines using the Graft CLI runtime. Compose agent graphs, state handoffs, and verification steps into repeatable workflows. Use when orchestrating cooperating agents."
---

> **This skill needs Graft, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.

# Graft Multi-Agent Pipeline Compiler

Declarative multi-agent orchestration runtime and compiler CLI. Graft lets developers define agent state machines, tool access policies, and validation gates in structured configuration files.

## Use this skill when
- Composing pipelines where multiple specialized agents collaborate sequentially or in parallel.
- Setting explicit handoff schemas and validation gates between agent stages.
- Replaying and debugging multi-step agent execution traces.

## Steps
1. **Initialize a Graft pipeline project**:
   Scaffold pipeline configuration:
   ```bash
   graft init my-agent-pipeline
   ```
2. **Define agent nodes and edges**:
   Specify agents, tasks, and transition conditions in `graft.yaml`:
   ```yaml
   pipeline:
     - name: researcher
       role: "Codebase exploration"
       output: "context.json"
     - name: implementer
       depends_on: [researcher]
       role: "Code authoring"
   ```
3. **Validate pipeline graph**:
   Run schema and dependency cycle checks:
   ```bash
   graft check graft.yaml
   ```
4. **Execute pipeline run**:
   Execute the compiled pipeline with live logging:
   ```bash
   graft run graft.yaml --log-level info
   ```

## Checks
- Verify graph has no circular dependencies or unresolvable transitions.
- Check that output schemas match input contracts of downstream nodes.

## Pitfalls
- Ensure environment variables and API credentials required by subagents are declared in project secrets.
- Always include explicit fallback and timeout transitions on long-running tasks.

## Sources
- [Graft GitHub Repository](https://github.com/JSLEEKR/graft)
