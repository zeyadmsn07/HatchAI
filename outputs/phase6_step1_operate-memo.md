# Phase 6 — Operate & learn: An AI-powered flashcard and spaced-repetition study tool for university students

## Real data (as of this run)

| Metric | Value | Source |
|---|---|---|
| Waitlist sign-ups | 0 | MVP not yet run by the founder (no app.db) |
| Unique visitors | 0 | STUBBED — no analytics connector yet |
| Test-mode orders (simulation) | 6 | sale-to-cash simulation, MOCKED |
| Test-mode refunds (simulation) | 6 | sale-to-cash simulation, MOCKED |

## Pre-registered rule (from Phase 2)

GO if >= 10% of >= 300 unique visitors sign up within 14 days; STOP if < 3% — channel: Community posts + up to USD 50.0 of targeted ads to the Phase 3 MVP landing page; 14 days; budget USD 50.0.
Status: **NOT_RUN**.

## Decision: **INSUFFICIENT_DATA**

0 visitors < 300 required; keep the test running.

## Next actions (each needs founder approval)

1. Approve and post the Phase 5 launch drafts in the two named communities.
2. Run the MVP (`python server.py` in the generated folder) so sign-ups are recorded in `app.db`.
3. Re-run Phase 6 after 14 days; the rule above decides PERSEVERE / PIVOT / STOP.

## How the rule would decide — SYNTHETIC inputs (illustration only, not results)

| Sign-ups | Visitors | Decision |
|---|---|---|
| 45 | 320 | PERSEVERE |
| 20 | 400 | PIVOT |
| 5 | 350 | STOP |
| 12 | 90 | INSUFFICIENT_DATA |
