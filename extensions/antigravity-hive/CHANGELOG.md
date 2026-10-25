# Changelog

## 0.3.0

- **Automatic skills.** The agent gets the skills SFP Hive chooses without copying anything: the extension keeps `.agents/rules/sfp-active-skills.md` in the workspace up to date with the chosen skills, in order, and the path of each `SKILL.md`. From activity alone it gives the phase's best bundle plus only the skills the hive is sure of. Turn it off with "Turn automatic skills on or off".
- **Skill history** in Insights: which skills the agent got, for which prompt or phase, and when (stored locally).
- **Skill Library** tab: 11 areas, 36 bundles, goals and clusters, search with highlighting, a detail page per skill, and "Add a skill from Git".
- **Now** tab: current phase with confidence, likely next phases, loaded bundles, and auto refresh.
- **Models** view: local models found automatically, a local router with failover, and a connection check (`doctor`).
- One consistent layout across all views; fixes for a Library tab that never loaded, a Now tab that never updated by itself, and a stale index on Windows.

## 0.2.0

- One extension with the `@hive` chat participant, the studio view and the Train command.
