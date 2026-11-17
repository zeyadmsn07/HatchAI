# Phase 6 — Operate & learn: An AI-powered flashcard and spaced-repetition study tool for university students

> Evidence mode: REPLAY of evidence_snapshots/strong_scenario.json (captured 2026-11-17T15:52:54+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

## Real traffic (the only input to the decision)

| Metric | Value | Source |
|---|---|---|
| Unique visitors | 0 | demo-strong/app.db (read via the MVP's Store.metrics()) |
| Page visits | 0 | same |
| Waitlist sign-ups (consented) | 0 | same |
| Test-mode orders (simulation) | 1 | sale-to-cash simulation, MOCKED |
| Test-mode refunds (simulation) | 1 | sale-to-cash simulation, MOCKED |

## Pre-registered rule (stored in Phase 2)

Minimum 300 unique visitors; PERSEVERE if sign-up rate ≥ 10%;
STOP if < 3%; PIVOT in between. Channel: Community posts + up to USD 50.0 of targeted ads to the Phase 3 MVP landing page; 14 days;
budget USD 50.0. Demand-test status: **NOT_RUN**.

## Decision on real traffic: **INSUFFICIENT_DATA**

0 unique visitors < 300 required by the pre-registered rule.

## TEST traffic — pipeline check, NOT demand

| Metric | TEST value |
|---|---|
| Page visits | 300 |
| Unique visitors | 300 |
| Waitlist sign-ups (consented, @example.com) | 20 |

Rule applied to TEST data: **PIVOT** — sign-up rate 6.7% between 3% and 10% (20/300).
This only proves that visits and sign-ups are recorded, stored, read back and fed through
the rule correctly. **It is not evidence of demand and is excluded from the decision above.**

## Next actions (each needs founder approval)

1. Approve and post the Phase 5 launch drafts in the two named communities.
2. Run the MVP with its persistent database (`python server.py --db app.db` in the generated folder).
3. Re-measure after 14 days: `python orchestrator.py measure <run_id>`.

## How the rule would decide — SYNTHETIC inputs (illustration only, not results)

| Sign-ups | Unique visitors | Decision |
|---|---|---|
| 45 | 320 | PERSEVERE |
| 20 | 400 | PIVOT |
| 5 | 350 | STOP |
| 12 | 90 | INSUFFICIENT_DATA |
