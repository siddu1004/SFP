---
name: toon
description: "Token-Oriented Object Notation (TOON) for passing structured data to LLMs with 30-60% reduced token costs and improved reliability compared to JSON/YAML. Use when formatting prompt payloads, structured agent outputs, or tabular data."
---

# TOON (Token-Oriented Object Notation)

TOON is a compact, human-readable serialization format specifically designed for passing structured data to Large Language Models with reduced token costs and improved extraction reliability.

## Format Overview

TOON achieves 30-60% token reduction over standard JSON and YAML by:
- Eliminating repeated keys across collections of records
- Removing redundant quotation marks and braces
- Providing deterministic parsing rules for primitives (strings, numbers, booleans, null)

## Syntax Guide

### Key-Value Objects
```toon
project: SFP
version: 3.4.0
status: active
```

### Lists and Sequences
```toon
skills:
  - frontend
  - backend
  - testing-quality
```

### Tabular Objects (Record Collections)
For arrays of uniform objects, declare fields once in brackets:
```toon
users[id, name, role, active]:
  1, Alice, admin, true
  2, Bob, developer, true
  3, Charlie, viewer, false
```

### Nested Structures
```toon
server:
  host: 127.0.0.1
  port: 8080
routes[path, method, handler]:
  /health, GET, checkHealth
  /api/skills, GET, listSkills
  /api/sync, POST, runSync
```

## Prompt Engineering with TOON

### Sending Data to LLMs (Context Injection)
When providing context data to an LLM:
```text
Here is the dataset in TOON format:
---
products[sku, name, price, stock]:
  A101, Widget Pro, 29.99, 142
  A102, Widget Mini, 14.99, 85
---
Analyze the inventory levels above.
```

### Requesting TOON Output from LLMs
Prompt instruction:
```text
Respond ONLY with valid TOON format representing the extracted records:
records[field1, field2, field3]:
  val1, val2, val3
```
