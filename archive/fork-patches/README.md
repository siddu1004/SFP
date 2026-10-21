# Fork patches

These are the commits that siddu1004's forks of the SFP source projects held and the original projects did not. They are saved here as patch files, so nothing is lost if a fork is deleted. SFP itself does not use them: it reads the original projects.

Apply one set on top of the matching original project at the base commit below:

```bash
git clone https://github.com/<original owner>/<project>.git && cd <project>
git checkout <base commit>
git am /path/to/SFP/archive/fork-patches/<folder>/*.patch
```

| Folder | Original project | Base commit | What the patches do |
|---|---|---|---|
| `OmniRoute` | diegosouzapw/OmniRoute | `7c92b155f76e` | A plugin manifest, a cloud-sync scheduler fix (runs the scheduled sync in-process instead of an unauthenticated self-fetch), its changelog entry, and loading the Claude plugin from the slim `claude-plugin` branch. The last three are the owner's own work. |
| `career-ops-for-claude-skill` | career-ops-hq/career-ops | `bac59f7b2b4c` | Keeps your CV, tracker and reports outside a plugin cache. SFP carries an updated version of this fix in `templates/career/patches/data-root.patch`. |
| `awesome-design-skills` | bergside/awesome-design-skills | `f631a09b4fcc` | A Claude Code plugin manifest, a Vercel web interface guidelines review command and a version bump. |
| `Agent-Reach` | Panniantong/Agent-Reach | `94f06c1969df` | A Claude Code plugin manifest. |
| `strix` | usestrix/strix | `972f5097c2bf` | A Claude Code plugin manifest. |
| `skills-claude-antigravity` | emilkowalski/skills | `2d228630ba14` | A Claude Code plugin manifest and marketplace file. |
| `impeccable` | pbakaus/impeccable | `dad8dbb3aac2` | A README note for installing from the fork. |
| `taste-skill-for-claude-and-antigravity` | Imaidazo/taste-skill-plugin | `02f67c2e7473` | A README note for installing from the fork. |

The plugin-manifest patches only made each fork installable as its own Claude Code plugin. SFP's category plugins replace that, so they are kept here for the record only.
