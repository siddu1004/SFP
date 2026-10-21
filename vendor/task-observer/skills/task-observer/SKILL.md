---
name: task-observer
description: "Use when the user corrects how Claude works or states a lasting preference (style, tools, conventions), to record it so later sessions follow it."
---

# Task Observer

Turn the user's corrections into project rules that Claude Code loads in every session.

Claude Code reads `CLAUDE.md` in the project root at the start of each session. This skill keeps a `## Working preferences` section in that file.

## Notice a lasting preference

Examples: "always use pnpm", "don't add comments to obvious code", "tests go next to the file", "answer in Romanian", "never touch the generated folder". A one-off instruction for the current task is not a lasting preference.

## Record it

1. Write the rule as one short, specific, imperative line: `- Use pnpm, never npm or yarn.`
2. Show it to the user and ask whether to save it to `CLAUDE.md` (project, shared with the team through git) or `CLAUDE.local.md` (only for them, should be git-ignored).
3. After they agree, add it under `## Working preferences`, creating the section if needed. If a rule on the same topic exists, replace it instead of adding a contradicting one.
4. Never record secrets or personal data.

## Review

When the user asks what Claude has learned, show the section. Offer to remove rules that are outdated or that the user no longer wants. Keep the section short; merge similar rules.
