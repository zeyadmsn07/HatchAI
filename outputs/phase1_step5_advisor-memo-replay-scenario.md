# Phase 1 — Advisor memo (after Gate 1: GO)

> Evidence mode: REPLAY of evidence_snapshots/repeat_scenario.json (captured 2026-11-17T15:31:37+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

> **Advisory only.** This memo interprets the stored results; it never changes E, V, the gate outcome or
> the pivot the gate proposes. Every sentence cites a verified source key (S…) or says ASSUMPTION;
> **0** sentence(s) failed that check and were removed.

## 1. What the evidence says the pain is

- S2 is the verified demand evidence, but it describes the market, not a pain: 'Ask HN: Books to learn about Arabic text processing — Hacker News thread with 2 points and 3 comments, posted 2023-06-14'.
- ASSUMPTION: the pain this product targets has not been observed in any source; it is inferred from the idea itself.

## 2. Does the current plan address it?

- ASSUMPTION: there is no verified pain to check the plan against, so product-problem fit is untested; the demand test in Phase 6 is the first real check.

## 3. Weakest assumption

- Demand evidence rests only on vendor or stale sources (S2, S14).

Other gaps:

- Pricing evidence rests only on vendor or stale sources (S19).
- Channel evidence rests only on vendor or stale sources (S14, S22).

### Evidence-specific risks (from the evidence audit)

- Pricing rests on vendor sources (S19), which quote their own prices. ASSUMPTION (kill criterion): fewer than 3 of 10 target users say they would pay the entry price. ASSUMPTION (cheapest test): ask them before building any paid tier.
- S2 (demand) dates from 2023-06-14, so the plan built on it is untested today. ASSUMPTION (kill criterion): the channel or fact cannot be confirmed by one current source.
- 55% of verified quotes (S14, S15, S19, S22) come from search snippets, not the page. ASSUMPTION (cheapest test): open those pages and confirm the sentence is there in context.

## 4. Cheapest test this week

- ASSUMPTION (proposed test, USD 0, 1 week): interview 5 target users in Jordan about the last time they had this problem and what they did about it, then share the MVP landing page and count consented waitlist sign-ups.
- Channels with verified evidence to start from: S14, S22.

## 5. What would change the recommendation

- No single source (S2, S3, S4, S14, S15, S17, S19, S22) changes the Gate 1 outcome when removed, so the recommendation does not hinge on one page.

Each row re-runs the Gate 1 function with one cited source removed (computed by code):

| Source removed | E without it | Gate outcome | vs. now |
|---|---|---|---|
| S2 | 95.0 | GO | same |
| S3 | 100.0 | GO | same |
| S4 | 100.0 | GO | same |
| S14 | 100.0 | GO | same |
| S15 | 100.0 | GO | same |
| S17 | 100.0 | GO | same |
| S19 | 92.0 | GO | same |
| S22 | 100.0 | GO | same |

## Evidence-based angles

- ASSUMPTION: the verified evidence shows no gap that competitors leave open; no angle is proposed rather than inventing one.

## Model-written summary (optional)

Not produced (LLM mode: LLM_DISABLED; enable with HATCHAI_ADVISOR_LLM=1 and a local model). The sections above are rule-based and complete without it.
