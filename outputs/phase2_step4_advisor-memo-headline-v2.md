# Phase 2 — Advisor memo (after Gate 2: GO)

> Evidence mode: REPLAY of evidence_snapshots/strong_v2_scenario.json (captured 2026-11-17T20:51:46+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v2 (relevance: brief-specific user / problem / local terms)

> **Advisory only.** This memo interprets the stored results; it never changes E, V, the gate outcome or
> the pivot the gate proposes. Every sentence cites a verified source key (S…) or says ASSUMPTION;
> **0** sentence(s) failed that check and were removed.

## 1. What the evidence says the pain is

- S12 is the verified demand evidence, but it describes the market, not a pain: '8 hours ago · The study noted that students enrolled in pre-university education account for more than 25% of Egypt's population, ranging from kindergarten to…'.
- ASSUMPTION: the pain this product targets has not been observed in any source; it is inferred from the idea itself.

## 2. Does the current plan address it?

- ASSUMPTION: there is no verified pain to check the plan against, so product-problem fit is untested; the demand test in Phase 6 is the first real check.

## 3. Weakest assumption

- Demand rests on a single source (S12); one misread page would remove the only evidence that anyone has the problem.

Other gaps:

- ASSUMPTION: pricing has no verified source.
- Competitor evidence rests only on vendor or stale sources (S13, S16).

### Evidence-specific risks (from the evidence audit)

- ASSUMPTION: no verified price exists, so the price is an estimate. ASSUMPTION (kill criterion): fewer than 3 of 10 target users accept the entry price when asked directly.
- S24 (channels) dates from 2015-09-09, so the plan built on it is untested today. ASSUMPTION (kill criterion): the channel or fact cannot be confirmed by one current source.
- 57% of verified quotes (S9, S12, S13, S24) come from search snippets, not the page. ASSUMPTION (cheapest test): open those pages and confirm the sentence is there in context.
- ASSUMPTION (from the Phase 2 critique): Target users will pay a recurring price; kill criterion: If fewer than 3% of landing-page visitors click a priced plan, stop or pivot pricing.

## 4. Cheapest test this week

- ASSUMPTION (proposed test, USD 0, 1 week): interview 5 university students in Egypt about the last time they had this problem and what they did about it, then share the MVP landing page and count consented waitlist sign-ups.
- Channels with verified evidence to start from: S9, S24.
- ASSUMPTION: the pre-registered rule then decides in Phase 6 (at least 300 unique visitors; persevere at ≥ 10% sign-ups, stop below 3%).

## 5. What would change the recommendation

- No single source (S3, S4, S9, S12, S13, S16, S24) changes the Gate 2 outcome when removed, so the recommendation does not hinge on one page.

Each row re-runs the Gate 2 function with one cited source removed (computed by code):

| Source removed | E without it | Gate outcome | vs. now |
|---|---|---|---|
| S3 | 83.4 | GO | same |
| S4 | 83.4 | GO | same |
| S9 | 83.4 | GO | same |
| S12 | 75.4 | GO | same |
| S13 | 83.4 | GO | same |
| S16 | 83.4 | GO | same |
| S24 | 83.4 | GO | same |

## Evidence-based angles

- The verified competitor sources (S13, S16) never mention Egypt or Arabic, while S3, S4, S9, S12 do: a localised version is an underserved segment.

## Model-written summary (optional)

Not produced (LLM mode: LLM_DISABLED; enable with HATCHAI_ADVISOR_LLM=1 and a local model). The sections above are rule-based and complete without it.
