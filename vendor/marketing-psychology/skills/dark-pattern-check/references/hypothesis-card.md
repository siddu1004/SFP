# Hypothesis card

Use this instead of predicting a result. Test design, sample size and readouts are out of scope for this plugin.

```
Hypothesis: Because [mechanism, ledger id, grade] addresses [barrier, quoted from the input],
changing [one element: before -> after] should raise [primary metric] for [segment].
Legitimate only if: [the fact that must be true]
Variant: one change against the current version
Guardrails: [pick: refunds, cancellations within 30 days, chargebacks, complaints, unsubscribes]
Decision rule: a lift on the primary metric together with a guardrail breach counts as a failed test.
How to test: To size and read this test, use a conversion-rate-optimisation (A/B testing) skill, a sample-size tool or your experimentation platform.
Feasibility: At scale, nudge-type changes averaged +1.4 percentage points, an 8.0% relative increase (L21).
Effects that small usually take more than ten thousand visitors per version to detect. On lower traffic,
ship only honest, low-risk changes and claim no lift.
```

Rules:
- One mechanism and one change per card; the ledger id and grade are mandatory. For a friction or enablement fix, give the framework id (L27, L28, L32) and "no effect grade".
- Guardrails come from L31: a change that lifts sign-ups while raising refunds or complaints has not worked.
- Never add a sample size, duration, power figure or significance threshold.
- When the evidence grade is D, do not write a card; say why and suggest a change with a better-supported mechanism or a friction fix.
