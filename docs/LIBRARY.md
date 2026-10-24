# The skill library: what skills do, and bundles

819 skills are too many to browse by name. The library groups them three ways, in the sidebar and in `sfp_hive.py library`:

- **What it does** (15 purposes): the job the skill is for, such as "Test and verify" or "Deploy and release".
- **Clusters** (about 40): the topic, such as "Animation and motion" or "GSD project workflow". See `clusters.json`.
- **Bundles**: named, ordered sets of skills that go together for one job. Applying one pins its skills into the hive's choice for the task.

Search covers all of it.

## Purposes

| Purpose | What it is for | Skills |
|---|---|---|
| Design interfaces | Make interfaces look and feel right: visual style, components, motion and accessibility. | 137 |
| Build features | Write the code: frameworks, languages, APIs, data and integrations. | 82 |
| Test and verify | Write tests and check that things work. | 34 |
| Debug and fix | Find the cause of a failure and repair it. | 6 |
| Secure and audit | Find and close security holes; privacy and compliance. | 21 |
| Review and refactor | Review changes, enforce quality and clean up code. | 49 |
| Speed up and cut cost | Make it faster, smaller or cheaper, including tokens. | 34 |
| Deploy and release | Ship it: containers, CI, infrastructure and releases. | 17 |
| Plan and architect | Decide what to build and how: plans, specs, architecture and decisions. | 72 |
| Research and understand | Learn a codebase, a topic or a market before acting. | 45 |
| Document and explain | Write docs, records and reports. | 6 |
| Run agents and workflows | Orchestrate agents, loops, automations, memory and gateways. | 117 |
| Build skills, plugins and MCP | Extend the agent itself: skills, plugins, hooks and MCP servers. | 31 |
| Create content, media and 3D | Produce writing, video, social posts, Blender scenes and other media. | 134 |
| Run the business | Finance, operations, planning for teams, industry work and careers. | 34 |

### How a skill gets its purpose

`purposes.json` holds the rules, and `mcp/sfp_library.py` applies them in this order:

1. An entry in `names` (empty for now: it is the place for a correction).
2. The first `name_rx` pattern that matches the skill's name, such as `test`, `security`, `deploy` or `research` as a whole word, or a name ending in `-patterns`.
3. The skill's home cluster. A cluster either has one fixed purpose (Security is "Secure and audit"), or is marked `by_phase`: its default purpose stands unless the skill's *name* contains a word for another job (the hive's eleven phases of work map to purposes). A job word found only in the description never changes the default, because words like "error" and "performance" turn up in almost every description.

Up to two secondary purposes come from the skill's other clusters and its second-strongest job. The interface shows the primary one and lets you filter by either.

### How accurate it is

One person (the author) labelled skills by reading their descriptions. Some labels are arguable, and a skill often serves more than one purpose, so the numbers show how often the primary purpose matches one labeller's choice, not a ground truth.

| Set | Skills | Primary purpose matches |
|---|---|---|
| Dev: the rules were tuned on these | 120 | 100 (83%) |
| Held-out: labelled before the second round of rules | 40 | 31 (77%) |

The first round of rules scored 76% on the first 80 dev skills and 57% on a first held-out set. Looking at that set's mistakes, I tightened the rules (the description-never-overrides rule above came from it), added its 40 skills to the dev set, and labelled the 40 fresh ones before changing anything else. A skill that is wrongly placed is still found by search, by cluster, and by pinning it, and `purposes.json` `names` fixes one.

## Bundles

Bundles live in `bundles.json`. Eighteen of them are the hive's own recipes (`mcp/stack_recipes.json`), shown here by reference so there is one source: the hive also uses those recipes to seed its predictions. The rest are curated sets. Every skill named is checked against the catalog by `tests/test_library.py`.

| Bundle | Purpose | Skills in order | For |
|---|---|---|---|
| Ship a page | design | `design-taste-frontend`, `impeccable`, `accessibility-audit`, `break-ui` | A new page or screen that has to look right and work for everyone. |
| Polish motion | design | `animate`, `review-animations`, `animation-performance` | The UI works but the motion feels cheap or heavy. |
| Critique a ui | design | `design-critique`, `ux-writing`, `accessibility-audit` | You want an honest review of a finished interface. |
| React feature | build | `react-patterns`, `react-testing`, `e2e-testing`, `react-performance` | A new feature in a React or Next.js app. |
| Flutter screen | build | `dart-flutter-patterns`, `flutter-dart-code-review` | A new screen in a Flutter app. |
| Django feature | build | `django-patterns`, `django-tdd`, `django-security` | A new feature in a Django project. |
| Fastapi feature | build | `fastapi-patterns`, `python-testing`, `security-review` | A new endpoint or service in FastAPI. |
| Go service | build | `golang-patterns`, `golang-testing` | A new Go service or a change to one. |
| Ship a service | deploy | `api-design`, `database-migrations`, `tdd-workflow`, `security-review` | A backend service that is ready to go live. |
| Containerize and deploy | deploy | `docker-patterns`, `deployment-patterns`, `canary-watch` | Put an app in a container and deploy it. |
| Postgres change | build | `postgres-patterns`, `database-migrations`, `verification-loop` | A schema or query change on Postgres. |
| Harden an app | secure | `find-security-vulnerabilities-in-code`, `owasp-top-10-testing`, `penetration-testing-with-strix`, `security-review` | An app is about to face real users or an audit. |
| Build a plugin | extend | `skill-creator`, `hook-development`, `mcp-builder`, `agent-eval` | Building a plugin or skill for an agent. |
| Mcp server | extend | `mcp-server-patterns`, `mcp-builder`, `mcp-dependency-review` | Building an MCP server. |
| Join a codebase | research | `codebase-onboarding`, `code-tour`, `architecture-decision-records` | You are new to a codebase and need to understand it fast. |
| Research then build | research | `deep-research`, `search-first`, `blueprint` | The problem is not understood yet. |
| Fundraise | business | `market-research`, `investor-materials`, `investor-outreach` | Preparing to raise money. |
| Publish content | create | `article-writing`, `seo`, `content-engine` | Writing and publishing an article or post. |
| Add tests to legacy code | test | `investigate-first`, `tdd-workflow`, `python-testing`, `safe-refactor`, `verification-loop` | Code has no tests and you must change it. |
| Table-driven Go tests | test | `golang-testing`, `tdd-workflow`, `verification-loop` | Writing tests for Go code. |
| End-to-end test suite | test | `e2e-testing`, `browser-qa`, `click-path-audit`, `react-testing` | A web app has no end-to-end coverage. |
| Accessible form | design | `frontend-a11y`, `ux-writing`, `react-patterns`, `accessibility-audit` | Building or fixing a form. |
| Audit dependencies | secure | `security-scan`, `application-security-testing`, `security-review`, `verification-loop` | Before a release or after a security notice. |
| Prepare a release | deploy | `verification-loop`, `git-workflow`, `mem-release`, `deployment-patterns`, `canary-watch` | A release is due. |
| Fix a bug properly | debug | `investigate-first`, `orch-fix-defect`, `surgical-patch`, `verify-and-stop` | A bug report with steps to reproduce. |
| Speed up a React app | speed | `benchmark`, `react-performance`, `animation-performance` | A React or Next.js app feels slow. |
| Cut agent token spend | speed | `context-budget`, `token-budget-advisor`, `strategic-compact`, `caveman`, `toon` | Sessions run out of context or cost too much. |
| Onboard to a codebase | research | `codebase-onboarding`, `repo-scan`, `engineering-graphify`, `mem-learn-codebase` | First day on a project. |
| Market and competitor scan | research | `deep-research`, `market-research`, `competitive-report-structure` | Before a product or investment decision. |
| Documentation pass | document | `documentation-lookup`, `docs-governance`, `architecture-decision-records` | Docs have drifted from the code. |
| Run an agent team | agents | `orch-pipeline`, `team-agent-orchestration`, `continuous-agent-loop`, `santa-method` | A big task you want split across agents. |
| Memory across sessions | agents | `unified-memory`, `continuous-learning-v2`, `mem-search`, `mem-smart-explore` | The agent keeps forgetting earlier work. |
| 3D and shader effects for the web | design | `react-three-fiber`, `shadergradient`, `liquid-glass-js`, `animation-performance` | A hero section or product viewer with depth. |
| Write and promote | create | `article-writing`, `seo`, `content-engine`, `brand-voice` | Launching content. |

Your own bundles are kept in your data folder (`bundles.json` next to `decisions.jsonl`):

```bash
python3 mcp/sfp_hive.py bundles                       # list them
python3 mcp/sfp_hive.py bundle-add "My page kit" --skills impeccable,frontend-a11y --purpose design --goal "what I use for pages"
python3 mcp/sfp_hive.py bundle-remove "My page kit"
python3 mcp/sfp_hive.py select "add a signup page" --bundle ship-a-page    # pin a bundle's skills for this task
```

A pinned skill is listed as "pinned by you". Feedback on that decision still teaches the hive, so a bundle skill you mark unhelpful for a kind of task is down-weighted next time.

## What the editor reads

`sfp_hive.py library` prints one JSON object (about 400 KB, in about 0.2 s): the purposes, clusters and bundles, and every skill with a one-line description, its purpose, cluster, usage counts, and the words search uses (its name and its most telling description words, in the same stemmed form as the Python search). `extensions/antigravity-hive/src/library.ts` searches and groups that object without calling Python again: a query takes a few milliseconds.

Search ranks a whole word in the skill's name first, then the start of one, then a related word (accessible and accessibility), then the skill's purpose or cluster, then its description, and allows one typo in words of five letters or more. A skill matching more of the query ranks higher, and shorter names win ties.
