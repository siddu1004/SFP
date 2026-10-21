# Product Thinking

This is the case for turning SFP's selection and learning into something people pay for, and what would have to be true. It is analysis, not a plan that is under way. The engineering is in [SELECTION.md](SELECTION.md).

## What is worth paying for

The skills themselves are free and open, and most are other people's work under MIT or Apache-2.0. Reselling them is not a business, and it would rightly annoy their authors. What people would pay for is judgement: picking the right few skills for this task in this codebase, learning from corrections, and showing that it worked.

## Who pays, and why

| Customer | Pain | What they get |
|---|---|---|
| Individual developer | The agent gets slower and vaguer as skills pile up, and repeats the same wrong choice | Free: selection, recipes, local learning |
| Team lead | Every developer's agent works differently, and reviews catch the same mistakes | Shared team selections ("how we ship a service here"), required checks such as `security-review` before any release, one learned model for the team |
| Platform or developer-experience team | Hundreds of internal and public skills, no idea which help | Analytics of which skills and selections helped, by project type; private skills indexed beside public ones; a way to retire skills that never help |
| Regulated company | Agents must follow compliance steps | Compliance selections that always apply for matching tasks, with an audit log of what was chosen and why |
| Skill authors | Hard to get a skill found and trusted | Selections ranked by measured outcomes, with revenue share on paid packs |

## Product shape

1. **Open core (today).** The selector, the feedback loop, the recipes, the router, the MCP server and local learning. Free, MIT. This is the distribution channel.
2. **Team.** A shared registry of selections and a shared learned model, synced to every IDE; team recipes; policies (always include, never include); private skill sources; aggregated outcomes. Priced per seat.
3. **Marketplace.** Creators publish selections ("Stripe payments", "Next.js SEO"), ranked by outcome data, not stars.
4. **Enterprise.** Self-hosted registry, single sign-on, audit logs, compliance selections, support.

## What could make it defensible

- **Outcome data.** Which selections helped, for which kinds of project, is data nobody else has. It improves the ranking, which brings more use, which brings more data. The feedback loop is how that data starts to exist.
- **One selector across IDEs.** Teams use several agents. A selector that behaves the same in Claude Code, Cursor, Codex and the rest is more useful than any one vendor's.
- **Proof.** The evaluation harness publishes its own numbers, including its failures. Extending it to task outcomes would make the claims checkable, which most tools in this space cannot offer.

## Risks, stated plainly

- **The IDEs may build this in.** Claude Code already picks skills by description. The answer has to be better choices across IDEs, team policy and outcome data, not routing alone.
- **The quality gain is not yet proven.** Until a task-outcome benchmark exists, the honest claim is "fewer, better-matched skills, and a reported mistake is not repeated", not "better code".
- **Feedback may not be given.** The loop only works if agents and people report. Cheap, automatic reporting by the agent at the end of a task matters more than the model.
- **Privacy.** Learning data is only valuable if teams trust it. Keep it local by default, share only the model or aggregated counts when a team opts in, and never share prompts or code.
- **Licenses.** Paid packs must respect each skill's license and credit its authors. Selections reference skills; they do not copy them.

## First steps to test the idea

1. Run the task-outcome benchmark and publish the result, good or bad.
2. Give five teams shared selections and policies, and measure how often they accept a selection, how often they report feedback, and how often the same mistake recurs.
3. Ask ten skill authors whether they would publish selections, and what would make them trust the ranking.
4. Price the team tier only after those numbers exist.
