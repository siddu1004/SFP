---
name: agentmemory
description: "Connect and configure the AgentMemory MCP vector server to store embeddings and retain persistent state across agent runs. Use when setting up long-term memory servers, vector state backends, or agent persistence infrastructure."
---

# AgentMemory Persistent Memory

Persistent semantic memory layer for AI agents powered by AgentMemory. Integrates as an MCP server to provide long-term associative memory, decision logging, and recall across IDE restarts.

## Use this skill when
- Setting up long-term memory servers, vector state backends, or agent persistence infrastructure.
- Retaining architectural decisions, project conventions, and user preferences across agent sessions.
- Preventing repetitive re-investigation in large codebases.

## Steps
1. **Start or register the AgentMemory MCP server**:
   Connect via stdio or SSE in your IDE configuration:
   ```bash
   npx -y @agentmemory/agentmemory
   ```
2. **Store new memories**:
   Call the `memory_store` tool with a category, key facts, and associative tags:
   - Provide concise, actionable summaries rather than raw conversation logs.
   - Tag with relevant languages, framework names, and module paths.
3. **Query existing vector memories**:
   Call `memory_search` with natural-language query terms before beginning complex tasks.
4. **Update or prune memories**:
   Review outdated facts and call `memory_update` or `memory_delete` to maintain high signal.

## Checks
- Verify MCP connection status in IDE settings.
- Test query retrieval with a known stored keyword.
- Check that stored memory entries do not contain sensitive credentials or API keys.

## Pitfalls
- Storing entire file contents clutters vector index; store only decisions, gotchas, and architectural invariants.
- Avoid duplicate memories by searching existing records before inserting new items.

## Sources
- [AgentMemory GitHub Repository](https://github.com/rohitg00/agentmemory)
