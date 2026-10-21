---
name: headroom
description: "Use when the user wants Claude to work with a document, log or data file too large to read whole, such as long specs, big logs or large JSON or CSV files."
---

# Headroom

Scripts: `${CLAUDE_SKILL_DIR}` is the folder that contains this file. If your agent does not define it, use the folder where this `SKILL.md` is located.

Work with very large files without filling the context: measure first, then read in pieces and keep a short digest.

## 1. Measure

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/peek.py <file>
```

It prints size, line count, an outline (Markdown headings, top-level JSON keys, CSV columns with a few sample rows, or the most frequent log line patterns) and the line numbers where each section starts. Use it to decide what to read.

## 2. Read only what the task needs

- Text and Markdown: read the sections from the outline by line range
- Logs: `grep -n` for the error, time window or request ID, then read a few lines around each hit
- JSON: extract the path you need (`python3 -c` with `json`, or `jq` if installed) instead of reading the file
- CSV: read the header and filter rows with a short script; compute counts and sums with code, not by reading rows

## 3. Keep a digest

For long documents, write what you learned to a digest file (for example `notes/<file>.digest.md`): key facts, numbers and the line ranges they came from. Refer back to the digest instead of re-reading the source. Cite line numbers so the user can check.
