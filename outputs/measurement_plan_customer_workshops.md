# Measurement plan: Customer workshops

**Answer.** Run a randomised holdout. The 10,000 eligible accounts are enough to detect a +25% uplift, which needs 7,834. In the simulated run the measured uplift was +24.5% (95% interval +7.9% to +43.6%), worth £3,564,000 against a sourced claim of £9,959,400.

All data in this report is fictional.

## Brief

| Item | Value |
| --- | --- |
| Programme | Customer workshops |
| Unit | account |
| Primary metric | Opportunity created within the outcome window |
| Eligible units | 10,000 |
| Baseline rate | 10.0% |
| Target uplift (relative) | +25.0% |
| Treated rate at target | 12.50% |
| Split (treated / held out) | 80 / 20 |
| Alpha | 0.05 |
| Power | 80% |
| Outcome window | 60 days |
| Average outcome value | £18,000 |
| Share of converters touched | 55% |

## Sample size

- Test: difference between two proportions, both tails, alpha 0.05, power 80%.
- Accounts per arm with an even split: 2,507.
- Adjustment for the 80/20 split: 1.5625x, from 1 / (4 × h × (1 − h)).
- Total needed: 7,834 (6,267 treated, 1,567 held out).
- Eligible: 10,000. That is enough.
- Power if every eligible account is used: 88.6%.
- Smallest uplift 10,000 accounts can detect: +22.0%.

## Design

**Randomised holdout.**

- Randomise at account level before any outreach.
- Treat 8,000 accounts. Hold out 2,000. The holdout gets no programme contact.
- Measure opportunity created within the outcome window for both groups over 60 days.
- Fix the metric, the test and the alpha before launch. Read the result once, at the end of the window.

## Simulated run

Fictional run with a true uplift of +30.0% (seed 7).

| Group | Units | Conversions | Rate |
| --- | ---: | ---: | ---: |
| Treated | 8,000 | 1,006 | 12.57% |
| Held out | 2,000 | 202 | 10.10% |

| Result | Value |
| --- | --- |
| Measured uplift | +24.5% (95% interval +7.9% to +43.6%) |
| p value | 0.002 |
| Significant at alpha 0.05 | Yes |
| Incremental conversions | 198 (range 77 to 319) |
| Incremental value | £3,564,000 (range £1,393,513 to £5,734,487) |
| Sourced claim | 553 conversions worth £9,959,400 |
| Sourced claim against measured value | 2.8x |

## How to read this

- The sourced count credits every converter the programme touched. It includes accounts that would have converted anyway.
- The holdout shows what happens without the programme. The gap between the two rates is the effect.
- The interval is the range of uplifts the data supports. If it includes zero, the run did not prove an effect.
- The value range comes from the interval on the rate difference, times the average outcome value.

## Guardrails

- Unsubscribe rate in the treated group stays below 0.5%.
- Holdout accounts receive no workshop invitations from any team.
- Sales cycle length in the treated group does not rise by more than 10%.

## Method notes

- Sample size uses the normal approximation for two proportions. The null uses the pooled variance.
- An uneven split scales the total by 1 / (4h(1 − h)). An 80/20 split needs 1.5625x the units of an even split.
- The uplift interval comes from the log risk ratio.
- The p value comes from a pooled z test with both tails.
