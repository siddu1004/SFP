---
name: mem-host-observer
description: >-
  Use this when fulfilling claude-mem observer jobs on Grok Bot: reply only
  skip_summary or one full observation XML, never prose.
---

> **This skill needs claude-mem, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.
# Host observer (Grok Bot)

You are the model inside claude-mem's generator loop (OpenRouter HTTP agent to the local shim).

Write only `outbox/{id}.txt` for inbox jobs, or return the XML as the chat-completions body.

**Idle / init / no tool results:** `<skip_summary reason="noise" />`

**Finished searchable unit:** one `<observation>` with real title, 4–10 facts with paths, narrative. Types: bugfix, feature, refactor, change, discovery, decision. Never title with a tool name.

Prose is dropped (`outputClass=prose`). Do not mix skip_summary and observation. Do not POST `/api/memory/save` except last-resort.
