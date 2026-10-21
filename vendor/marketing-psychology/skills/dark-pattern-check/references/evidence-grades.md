# Evidence grades and the evidence card

## Grades

| Grade | Meaning | How to word it |
|---|---|---|
| A | Robust: replicated across labs or in meta-analyses, and seen outside the lab | "Well supported" |
| B | Real, but smaller or more conditional in practice than the popular version | "Supported under these conditions: …" |
| C | Mixed or contested: meta-analyses disagree, or the effect shrinks in realistic settings | "Contested; test before relying on it" |
| D | Failed replication, or folklore with no study in the ledger | "Not supported" |
| P | Practitioner report: one company or channel, no sample size | "Someone reported this; treat it as a hypothesis" |

Rows marked framework, method, taxonomy or context in the ledger are tools for structuring work, not effects, and get no grade.

Grading rules:
- A grade belongs to the claim as the user stated it, not to the effect at its strongest. "Loss aversion exists" and "loss-framed buttons convert better" get separate cards.
- Lab evidence with hypothetical choices caps a marketing claim at B unless the ledger has field evidence for it.
- Never upgrade a grade because the user or a famous book asserts it.
- Take the grade from the ledger row. Where a row gives two grades (for example lab vs marketing outcome), say which one applies to the user's case and why.
- A claim that matches no ledger row: "not in this plugin's ledger", grade C at most, no reference, no number, plus one line on what evidence would settle it (a preregistered replication, a meta-analysis, a field test at scale).
- A practitioner number (a test result from a post, a case study, an agency deck) is P. If arm sizes are missing, say "cannot judge: arm sizes not given" and list what to ask for: visitors per arm, conversions per arm, test dates, how the winner was chosen.
- A study the user cites that is not in the ledger: "user-provided, not checked here". Do not upgrade or downgrade it from memory.
- The grade describes the general claim. Whether it works on the user's page is a separate question, answered only by their own test (`hypothesis-card.md`).

## Evidence card (one per claim, at most 8 per answer)

1. Claim, rewritten in testable form ("Showing a crossed-out higher price raises purchases of the discounted item").
2. Origin: the ledger study and what it measured (who took part, setting, outcome, real or hypothetical choice).
3. Replication and meta-analytic record from the ledger.
4. Field evidence at scale, if the ledger has any.
5. Grade with a one-line reason.
6. Holds when / fails when.
7. Accurate rewrite of the claim the user can safely repeat.
8. If the user wants to use it: a hypothesis card, and the rule rows it may engage.
