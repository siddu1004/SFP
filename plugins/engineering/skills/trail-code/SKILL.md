---
name: trail-code
description: "Track AST changes, record contextual codebase learnings, and monitor symbol references using Trail-Code. Use when recording code learnings during refactoring or building automated context trails."
---

> **This skill needs Trail-Code, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.

# Trail-Code AST Change & Learnings Tracker

Contextual learnings and AST dependency monitoring layer for AI coding agents. Trail-Code watches code edits, calculates AST differences, and records localized knowledge trails alongside source files.

## Use this skill when
- Recording gotchas, edge cases, and domain constraints alongside affected source files.
- Monitoring structural symbol drift during broad refactoring sessions.
- Automatically summarizing AST changes between test iterations.

## Steps
1. **Initialize Trail-Code tracking**:
   Initialize repository tracking metadata:
   ```bash
   npx trail-code init
   ```
2. **Start watcher daemon**:
   Watch source files for AST modifications in background:
   ```bash
   npx trail-code watch --dir src
   ```
3. **Record a codebase learning**:
   Attach an actionable learning note to a symbol or file:
   ```bash
   npx trail-code note src/auth/token.ts --symbol verifyJwt "Must handle expired token refresh within clock skew tolerance"
   ```
4. **Query active trails**:
   Retrieve recorded learnings for a module before modifying it:
   ```bash
   npx trail-code trail src/auth/token.ts
   ```

## Checks
- Verify `.trail/` configuration directory is properly initialized.
- Check that recorded notes accurately link to active symbol definitions.

## Pitfalls
- Avoid recording fleeting task notes; keep learnings focused on permanent codebase constraints.
- Ensure `.trail/` is committed to git so team members and future agents benefit from learnings.

## Sources
- [Trail-Code GitHub Repository](https://github.com/trailhq/Trail-Code)
