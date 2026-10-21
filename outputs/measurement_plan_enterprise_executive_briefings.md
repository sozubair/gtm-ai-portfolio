# Measurement plan: Enterprise executive briefings

**Answer.** Do not run a holdout. Detecting a +25% uplift needs 10,042 accounts and only 800 are eligible. Use a staged rollout. The smallest uplift this population can detect is +100%.

All data in this report is fictional.

## Brief

| Item | Value |
| --- | --- |
| Programme | Enterprise executive briefings |
| Unit | account |
| Primary metric | Opportunity created within the outcome window |
| Eligible units | 800 |
| Baseline rate | 8.0% |
| Target uplift (relative) | +25.0% |
| Treated rate at target | 10.00% |
| Split (treated / held out) | 80 / 20 |
| Alpha | 0.05 |
| Power | 80% |
| Outcome window | 90 days |
| Average outcome value | £95,000 |
| Share of converters touched | 70% |

## Sample size

- Test: difference between two proportions, both tails, alpha 0.05, power 80%.
- Accounts per arm with an even split: 3,213.
- Adjustment for the 80/20 split: 1.5625x, from 1 / (4 × h × (1 − h)).
- Total needed: 10,042 (8,033 treated, 2,009 held out).
- Eligible: 800. That is 9,242 short.
- Power if every eligible account is used: 12.1%.
- Smallest uplift 800 accounts can detect: +100.4%.

## Design

**Staged rollout.** A holdout this small cannot give a firm answer.

- Split the 800 accounts into waves at random.
- Launch the waves in a random order.
- Compare live waves with waves not yet live over the same window.
- Treat any measured uplift below +100.4% as directional only.
- If a firm answer is needed, pick an outcome with a higher base rate.

## Simulated run

Fictional run with a true uplift of +25.0% (seed 7). It shows what a holdout of this size would report. Read it as a picture of the noise.

| Group | Units | Conversions | Rate |
| --- | ---: | ---: | ---: |
| Treated | 640 | 50 | 7.81% |
| Held out | 160 | 14 | 8.75% |

| Result | Value |
| --- | --- |
| Measured uplift | −10.7% (95% interval −49.3% to +57.4%) |
| p value | 0.696 |
| Significant at alpha 0.05 | No |
| Incremental conversions | −6 (range −37 to 25) |
| Incremental value | −£570,000 (range −£3,516,932 to £2,376,932) |
| Sourced claim | 35 conversions worth £3,325,000 |
| Sourced claim against measured value | no measured value to compare |

## How to read this

- The sourced count credits every converter the programme touched. It includes accounts that would have converted anyway.
- The holdout shows what happens without the programme. The gap between the two rates is the effect.
- The interval is the range of uplifts the data supports. If it includes zero, the run did not prove an effect.
- The value range comes from the interval on the rate difference, times the average outcome value.

## Guardrails

- No account receives more than one briefing invitation a quarter.
- Account owners approve every invitation before it goes out.
- Win rate on briefed opportunities does not fall below the regional average.

## Method notes

- Sample size uses the normal approximation for two proportions. The null uses the pooled variance.
- An uneven split scales the total by 1 / (4h(1 − h)). An 80/20 split needs 1.5625x the units of an even split.
- The uplift interval comes from the log risk ratio.
- The p value comes from a pooled z test with both tails.
