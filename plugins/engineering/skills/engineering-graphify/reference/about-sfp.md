# About this skill in SFP

`SKILL.md` in this folder is Graphify's own skill file (`graphify/skill.md` in the upstream repository), copied by the SFP sync. The upstream project is [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify), licensed under Apache-2.0 (its `LICENSE`, with `NOTICE` and the older `LICENSE-MIT`). The licence is in `plugins/research-docs/LICENSES/graphify.txt` in the SFP repository.

Graphify itself is a Python program. The skill only drives it, so install the program first: from this folder run `python3 scripts/sfp_app.py status`, then `install` for the plan (it uses `uv tool install graphifyy`, or `pipx install graphifyy` when uv is missing), and `install --yes` after the user agrees. Then run `graphify install` once so Graphify registers its own hooks with the assistant, and `/graphify .` in the project.

`reference/readme.md` is the upstream README (install on each platform, commands, what the graph contains).
