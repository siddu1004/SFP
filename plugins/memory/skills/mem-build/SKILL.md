---
name: mem-build
description: Fully automate a coding task with make-plan, do, and babysit.
---

> **This skill needs claude-mem, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.

# Build

Deploy a subagent to fully automate a coding session as if it were typing in it itself.

Use these claude-mem skills in order:

1. `make-plan`
2. `do`
3. `babysit`

Task: $ARGUMENTS
