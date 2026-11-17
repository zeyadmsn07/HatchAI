# Phase 6 — Operate & learn: A booking app for Arabic calligraphy workshops for adult hobbyists in Jordan.

## Real traffic (the only input to the decision)

| Metric | Value | Source |
|---|---|---|
| Unique visitors | 0 | no MVP database yet (the MVP has not been run with a persistent app.db) |
| Page visits | 0 | same |
| Waitlist sign-ups (consented) | 0 | same |
| Test-mode orders (simulation) | 3 | sale-to-cash simulation, MOCKED |
| Test-mode refunds (simulation) | 3 | sale-to-cash simulation, MOCKED |

## Pre-registered rule (stored in Phase 2)

Minimum 300 unique visitors; PERSEVERE if sign-up rate ≥ 10%;
STOP if < 3%; PIVOT in between. Channel: Community posts + up to USD 20.0 of targeted ads to the Phase 3 MVP landing page; 14 days;
budget USD 20.0. Demand-test status: **NOT_RUN**.

## Decision on real traffic: **INSUFFICIENT_DATA**

0 unique visitors < 300 required by the pre-registered rule.

## TEST traffic — pipeline check, NOT demand

No TEST traffic recorded.

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
