# Phase 1 — Advisor memo (after Gate 1: REPEAT)

> Evidence mode: REPLAY of evidence_snapshots/strong_scenario.json (captured 2026-11-17T15:52:54+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v2 (relevance: brief-specific user / problem / local terms)

> **Advisory only.** This memo interprets the stored results; it never changes E, V, the gate outcome or
> the pivot the gate proposes. Every sentence cites a verified source key (S…) or says ASSUMPTION;
> **0** sentence(s) failed that check and were removed.

## 1. What the evidence says the pain is

- ASSUMPTION: no verified source describes demand or a pain for this brief, so the problem is the founder's hypothesis, not a finding.

## 2. Does the current plan address it?

- ASSUMPTION: there is no verified pain to check the plan against, so product-problem fit is untested; the demand test in Phase 6 is the first real check.

## 3. Weakest assumption

- ASSUMPTION: demand is the weakest link: no verified source shows that the target users have this problem.

Other gaps:

- Pricing evidence rests only on vendor or stale sources (S9, S13), so the price users would accept is untested today; confirm it with one independent, current source.
- Competitor evidence rests only on vendor or stale sources (S9, S11), so how crowded the market is is untested today; confirm it with one independent, current source.
- Channel evidence rests only on vendor or stale sources (S18, S19), so the plan to reach users is untested today; confirm it with one independent, current source.

### Evidence-specific risks (from the evidence audit)

- Pricing rests on vendor sources (S9, S13), which quote their own prices. ASSUMPTION (kill criterion): fewer than 3 of 10 target users say they would pay the entry price. ASSUMPTION (cheapest test): ask them before building any paid tier.
- 62% of verified quotes (S9, S11, S13, S18, S19) come from search snippets, not the page. ASSUMPTION (cheapest test): open those pages and confirm the sentence is there in context.

## 4. Cheapest test this week

- ASSUMPTION (proposed test, USD 0, 1 week): interview 5 university students in Egypt about the last time they had this problem and what they did about it, then share the MVP landing page and count consented waitlist sign-ups.
- Channels with verified evidence to start from: S18, S19.

## 5. What would change the recommendation

- No single source (S3, S4, S9, S11, S13, S18, S19) changes the Gate 1 outcome when removed, so the recommendation does not hinge on one page.

Each row re-runs the Gate 1 function with one cited source removed (computed by code):

| Source removed | E without it | Gate outcome | vs. now |
|---|---|---|---|
| S3 | 83.9 | REPEAT | same |
| S4 | 83.9 | REPEAT | same |
| S9 | 83.4 | REPEAT | same |
| S11 | 83.9 | REPEAT | same |
| S13 | 83.9 | REPEAT | same |
| S18 | 83.9 | REPEAT | same |
| S19 | 83.9 | REPEAT | same |

## Evidence-based angles

- The verified competitor sources (S9, S11) never mention Egypt or Arabic, while S3, S4, S18 do: a localised version is an underserved segment.
- Competitor prices in S9, S13, S15 have a median of USD 8.75/month, against a local affordability cap of USD 2.57/month from S4 (ASSUMPTION: cap = 1% of monthly GDP per capita): a free core with a low-cost tier is the price gap.
- S19 mentions institutions, so selling to them is an evidence-based option.

## Model-written summary (optional)

Not produced (LLM mode: LLM_DISABLED; enable with HATCHAI_ADVISOR_LLM=1 and a local or free-tier open-weight model). The sections above are rule-based and complete without it.
