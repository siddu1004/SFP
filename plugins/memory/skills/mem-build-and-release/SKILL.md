---
name: mem-build-and-release
description: Fully automate building and releasing a coding task.
---

> **This skill needs claude-mem, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.

# Build and Release

Deploy a subagent to fully automate a coding session as if it were typing in it itself.

Use these claude-mem skills in order:

1. `build`
2. Merge the ready PR and continue from updated main.
3. `release`

Task: $ARGUMENTS
