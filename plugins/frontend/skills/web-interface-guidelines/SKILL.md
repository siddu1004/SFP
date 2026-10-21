---
name: web-interface-guidelines
description: Review UI code against the Vercel Web Interface Guidelines (accessibility, focus states, forms, animation, typography, content handling, images, performance, navigation and state, touch, safe areas, dark mode, i18n, hydration, copy) and report terse file:line findings. Use when the user asks to review, lint or audit UI code or a component against web interface guidelines or UI best practices, or wants a pre-merge UI check.
---

# Web Interface Guidelines

A review checklist from [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) (MIT). The full rules and the output format are in `reference/rules.md`.

## Do

1. Take the files the user names (or, if none, the UI files changed in the current work).
2. Read `reference/rules.md`, read the files, and check them against the rules. Where the file says "Review these files for compliance: $ARGUMENTS", read it as the files from step 1.
3. Report in the format `reference/rules.md` gives: grouped by file, one `file:line - issue` per finding, terse, no preamble, `✓ pass` for clean files.

State the issue and its location. Skip explanation unless the fix is not obvious.
