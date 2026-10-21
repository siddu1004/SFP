# Price checks

All arithmetic is printed with its formula and inputs. Use the host's code tool when one is available; otherwise write "computed by hand, check the arithmetic". Money to two decimals, percentages to one decimal, rounding half away from zero.

## 1. Normalised table

| Figure | Formula |
|---|---|
| Monthly equivalent of an annual price | annual ÷ 12 |
| Annual saving, % | 1 − annual ÷ (monthly × 12) |
| Months free | 12 − annual ÷ monthly |
| Price per seat or unit | price ÷ seats (or units); "n.a." when unlimited |
| Price per day | monthly × 12 ÷ 365, always printed next to the billed amount and period (L10) |
| Step-up ratio between tiers | higher tier ÷ lower tier |

## 2. Anchor read

- Which price does the reader see first (layout order, mobile order)? The first large number seen acts as the reference (L02).
- Which plan is pre-selected or badged ("most popular", "recommended")? A badge needs a real basis (DP-03). A pre-selection that adds a recurring or higher charge goes to DP-10.

## 3. Decoy test (price is an attribute)

Option D is a decoy for target T when all of these hold (L14):
1. D costs the same as T or more;
2. D is equal or worse than T on every other listed attribute;
3. D is strictly worse than T on at least one attribute, price included;
4. D is not dominated in the same way by the other option the buyer is weighing (otherwise it is simply a bad option, not a decoy).

If the user gives only prices with no other attributes, write "decoy test not run: needs the feature list".

Per-unit price (per seat, per GB) is printed next to the matrix for information; it is not one of the attributes in the test, because the buyer pays the total.

Print the dominance matrix: one row per pair, columns for price and each listed attribute, each cell "better / same / worse" for the first option of the pair, and a last column "dominated?".

Worked example (fictional):

| Pair | Price | Seats | Reports | Dominated? |
|---|---|---|---|---|
| Pro-Lite ($79, 7 seats, no reports) vs Pro ($79, 10 seats, reports) | same | worse | worse | yes: Pro-Lite is dominated by Pro |
| Pro-Lite vs Basic ($29, 3 seats, no reports) | worse | better | same | no |

Result: Pro-Lite is a decoy for Pro (grade C, L14). If Pro-Lite cost $69 instead, it would be cheaper than Pro, so it is not dominated and not a decoy, even though its per-seat price ($9.86) is higher than Pro's ($7.90).

"No decoy present" is a common and valid result. The plugin does not propose decoys or new prices; it reports what the table already contains and what the evidence says about it. If the user asks for a decoy tier, it runs this test on the user's own proposal and states the L14 grade C caveat, without inventing a price.

## 4. Price endings

The left-digit effect applies only when the leftmost digit changes: $79 vs $80 changes it, $74 vs $75 does not (L06, grade B). Endings can also signal "discount quality", which may not suit a premium tier.

## 5. Discount framing

Print both the percent and the amount ("16.7% off" and "$158 off per year"). The "Rule of 100" (percent tends to look larger below a price of 100, the amount above it) is a heuristic, grade C (L13): suggest testing both rather than declaring a winner.

## 6. Rule cells

Check and list, with facts to confirm:
- "was" prices and percent-off claims: DP-05;
- fees outside the headline price: DP-06;
- pre-ticked paid extras: DP-07;
- trial, renewal and pre-selected billing period: DP-10;
- "most popular" or "recommended" badges: DP-03.

## 7. Data that would decide it

Name methods only; do not run them or invent results: Van Westendorp price sensitivity questions (L33), Gabor-Granger price ladders, conjoint analysis. Suggest separate reads for paying customers, churned customers and trial users who did not convert. This plugin does not set prices from costs or competitor prices.
