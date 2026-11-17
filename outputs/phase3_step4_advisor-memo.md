# Phase 3 — Advisor memo (after Gate 3: GO)

> Evidence mode: REPLAY of evidence_snapshots/strong_scenario.json (captured 2026-11-17T15:52:54+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

> **Advisory only.** This memo interprets the stored results; it never changes E, V, the gate outcome or
> the pivot the gate proposes. Every sentence cites a verified source key (S…) or says ASSUMPTION;
> **0** sentence(s) failed that check and were removed.

## 1. What the evidence says the pain is

- S6 (verified demand) names this pain: 'this preparation burden is so significant that it deters sustained adoption'.

## 2. Does the current plan address it?

- S6: no MVP feature addresses 'this preparation burden is so significant that it deters sustained adoption'.
- The MVP covers 0 of 1 verified pains (S6).

## 3. Weakest assumption

- Pricing evidence rests only on vendor or stale sources (S9, S15).

Other gaps:

- Competitor evidence rests only on vendor or stale sources (S9, S11).
- Channel evidence rests only on vendor or stale sources (S13, S19).

### Evidence-specific risks (from the evidence audit)

- Pricing rests on vendor sources (S9, S15), which quote their own prices. ASSUMPTION (kill criterion): fewer than 3 of 10 target users say they would pay the entry price. ASSUMPTION (cheapest test): ask them before building any paid tier.
- ASSUMPTION (from the Phase 2 critique): Target users will pay a recurring price; kill criterion: If fewer than 3% of landing-page visitors click a priced plan, stop or pivot pricing.

## 4. Cheapest test this week

- ASSUMPTION (proposed test, USD 0, 1 week): show the entry price next to a free core on the MVP landing page and ask 10 university students in Egypt whether they would pay it; record yes / no / why.
- Channels with verified evidence to start from: S13, S19.
- ASSUMPTION: the pre-registered rule then decides in Phase 6 (at least 300 unique visitors; persevere at ≥ 10% sign-ups, stop below 3%).

## 5. What would change the recommendation

- ASSUMPTION: Gate 3 depends only on the generated tests passing and the server booting; evidence cannot change it, but a failing test would turn it into REPEAT.


## Evidence-based angles

- S6 names 'this preparation burden is so significant that it deters sustained adoption', and none of the verified competitor sources (S9, S11) mention it: build the product around that pain.
- The verified competitor sources (S9, S11) never mention Egypt or Arabic, while S3, S4 do: a localised version is an underserved segment.
- Competitor prices in S9, S13, S15 have a median of USD 8.75/month, against a local affordability cap of USD 2.57/month from S4 (ASSUMPTION: cap = 1% of monthly GDP per capita): a free core with a low-cost tier is the price gap.
- S19 mentions institutions, so selling to them is an evidence-based option.

## Model-written summary (optional)

Not produced (LLM mode: LLM_DISABLED; enable with HATCHAI_ADVISOR_LLM=1 and a local model). The sections above are rule-based and complete without it.
