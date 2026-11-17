# Phase 1 — Advisor memo (after Gate 1: STOP)

> Evidence mode: REPLAY of evidence_snapshots/weak_scenario.json (captured 2026-11-17T15:53:01+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

> **Advisory only.** This memo interprets the stored results; it never changes E, V, the gate outcome or
> the pivot the gate proposes. Every sentence cites a verified source key (S…) or says ASSUMPTION;
> **0** sentence(s) failed that check and were removed.

## 1. What the evidence says the pain is

- S1 is the verified demand evidence, but it describes the market, not a pain: 'Maker of EpiPen to Sell Generic Version for Half the Price — Hacker News thread with 1 points and 1 comments, posted 2016-08-29'.
- ASSUMPTION: the pain this product targets has not been observed in any source; it is inferred from the idea itself.

## 2. Does the current plan address it?

- ASSUMPTION: there is no verified pain to check the plan against, so product-problem fit is untested; the demand test in Phase 6 is the first real check.

## 3. Weakest assumption

- Demand evidence rests only on vendor or stale sources (S1, S2), so whether anyone has the problem is untested today; confirm it with one independent, current source.

Other gaps:

- Pricing evidence rests only on vendor or stale sources (S8, S10), so the price users would accept is untested today; confirm it with one independent, current source.
- Local-constraint evidence rests only on vendor or stale sources (S7, S8), so whether users can access and pay is untested today; confirm it with one independent, current source.
- Channel evidence rests only on vendor or stale sources (S5, S7), so the plan to reach users is untested today; confirm it with one independent, current source.

### Evidence-specific risks (from the evidence audit)

- Pricing rests on vendor sources (S8, S10), which quote their own prices. ASSUMPTION (kill criterion): fewer than 3 of 10 target users say they would pay the entry price. ASSUMPTION (cheapest test): ask them before building any paid tier.
- S1 (demand) dates from 2016-08-29, so the plan built on it is untested today. ASSUMPTION (kill criterion): the channel or fact cannot be confirmed by one current source.
- S2 (demand) dates from 2016-12-16, so the plan built on it is untested today. ASSUMPTION (kill criterion): the channel or fact cannot be confirmed by one current source.

## 4. Cheapest test this week

- ASSUMPTION (proposed test, USD 0, 1 week): interview 5 target users about the last time they had this problem and what they did about it, then share the MVP landing page and count consented waitlist sign-ups.
- Channels with verified evidence to start from: S5, S7.

## 5. What would change the recommendation

- No single source (S1, S2, S3, S5, S7, S8, S10) changes the Gate 1 outcome when removed, so the recommendation does not hinge on one page.

Each row re-runs the Gate 1 function with one cited source removed (computed by code):

| Source removed | E without it | Gate outcome | vs. now |
|---|---|---|---|
| S1 | 95.0 | STOP | same |
| S2 | 95.0 | STOP | same |
| S3 | 95.0 | STOP | same |
| S5 | 95.0 | STOP | same |
| S7 | 95.0 | STOP | same |
| S8 | 95.0 | STOP | same |
| S10 | 95.0 | STOP | same |

## Evidence-based angles

- ASSUMPTION: the verified evidence shows no gap that competitors leave open; no angle is proposed rather than inventing one.

## Model-written summary (optional)

Not produced (LLM mode: LLM_DISABLED; enable with HATCHAI_ADVISOR_LLM=1 and a local or free-tier open-weight model). The sections above are rule-based and complete without it.
