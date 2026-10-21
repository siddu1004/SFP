---
name: mem-release
description: Fully automate a release with version-bump and childhood.
---

> **This skill needs claude-mem, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.

# Release

Deploy a subagent to fully automate a coding session as if it were typing in it itself.

Use these claude-mem skills in order:

1. `version-bump`
2. `childhood`

Task: $ARGUMENTS
