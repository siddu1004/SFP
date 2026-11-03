---
name: openviking
description: "Manage agent memory, knowledge, and context hierarchy using OpenViking's virtual filesystem (viking://). Use when structuring multi-tier agent context, managing persistent memory across sessions, or integrating agent filesystem RAG."
---

# OpenViking Context Filesystem

Structure agent memory, persistent project context, and knowledge bases using OpenViking (`volcengine/OpenViking`). OpenViking organizes agent context into a transparent, navigable virtual filesystem (`viking://`), providing multi-tier hierarchical context delivery (L0/L1/L2) to prevent context window bloat.

## Use This Skill When

- Managing long-term memory and session context across multiple agent runs.
- Navigating project knowledge graphs through standard filesystem semantics (`ls`, `cat`, `grep`).
- Integrating hierarchical RAG that loads high-level summaries first, fetching deep detail on demand.

## Core Concepts

- `viking://session/`: Current session memories and short-term dialogue buffer.
- `viking://project/`: Architectural decisions, code maps, conventions, and dependencies.
- `viking://skills/`: On-demand executable procedures and operational checklists.

## Usage & Operations

```bash
# Inspect agent virtual filesystem structure
viking ls viking://project/architecture

# Retrieve L0 summary (low-token overview)
viking cat --level=0 viking://project/overview

# Query memory with semantic search
viking search "database migration strategy"
```

## Checks & Verification

- [ ] Confirm hierarchical depth (L0 overview vs L2 full source) matches current agent task budget.
- [ ] Ensure stale session memories are pruned or compressed periodically.

## Sources

- [OpenViking Documentation](https://openviking.ai/)
- [OpenViking GitHub Repository](https://github.com/volcengine/OpenViking)
