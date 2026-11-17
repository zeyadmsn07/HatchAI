# Phase 2 — Red-team critique

> Evidence mode: REPLAY of evidence_snapshots/strong_v2_scenario.json (captured 2026-11-17T20:51:46+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v2 (relevance: brief-specific user / problem / local terms)

## Summary

4/5 evidence categories have verified, quoted sources (demand, competitors, local_constraints, channels). Gaps: pricing. Willingness to pay is untested until the pre-registered demand test runs.

## Viability score (computed by code): 4.0 / 5

| Component | Points |
|---|---|
| base | 1.0 |
| demand verified | 1.0 |
| competitors verified | 0.5 |
| pricing verified | 0.0 |
| local constraints verified | 0.5 |
| founder skills | 0.5 |
| founder time | 0.25 |
| risks testable | 0.25 |
| demand test passed | 0.0 |

## Demand signal

Egypt steps up pre-university education reform, expands ... reports: "8 hours ago · The study noted that students enrolled in pre-university education account for more than 25% of Egypt's population,  [S12]

## Founder fit

Skills: web development; 10.0 h/week; budget USD 500.0. Founder-fit points: 0.75

## Riskiest assumptions and kill criteria

| Assumption | Risk | Kill criterion | Evidence gaps |
|---|---|---|---|
| Target users will pay a recurring price | high | If fewer than 3% of landing-page visitors click a priced plan, stop or pivot pricing. | No primary willingness-to-pay data (demand test NOT_RUN) |

**Gate 2 recommendation:** GO
