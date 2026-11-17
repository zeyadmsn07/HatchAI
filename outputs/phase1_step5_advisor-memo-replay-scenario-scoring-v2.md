# Phase 1 — Advisor memo (after Gate 1: PIVOT)

> Evidence mode: REPLAY of evidence_snapshots/repeat_scenario.json (captured 2026-11-17T15:31:37+00:00); no evidence was collected in this run
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

- ASSUMPTION: pricing has no verified source.
- Competitor evidence rests only on vendor or stale sources (S17).
- Channel evidence rests only on vendor or stale sources (S21, S22).

### Evidence-specific risks (from the evidence audit)

- ASSUMPTION: no verified price exists, so the price is an estimate. ASSUMPTION (kill criterion): fewer than 3 of 10 target users accept the entry price when asked directly.

## 4. Cheapest test this week

- ASSUMPTION (proposed test, USD 0, 1 week): interview 5 target users in Jordan about the last time they had this problem and what they did about it, then share the MVP landing page and count consented waitlist sign-ups.
- Channels with verified evidence to start from: S21, S22.

## 5. What would change the recommendation

- No single source (S3, S4, S17, S21, S22) changes the Gate 1 outcome when removed, so the recommendation does not hinge on one page.

Each row re-runs the Gate 1 function with one cited source removed (computed by code):

| Source removed | E without it | Gate outcome | vs. now |
|---|---|---|---|
| S3 | 66.7 | PIVOT | same |
| S4 | 66.7 | PIVOT | same |
| S17 | 54.7 | PIVOT | same |
| S21 | 62.7 | PIVOT | same |
| S22 | 62.7 | PIVOT | same |

## Evidence-based angles

- ASSUMPTION: the verified evidence shows no gap that competitors leave open; no angle is proposed rather than inventing one.

## Model-written summary (optional)

Not produced (LLM mode: LLM_DISABLED; enable with HATCHAI_ADVISOR_LLM=1 and a local model). The sections above are rule-based and complete without it.
