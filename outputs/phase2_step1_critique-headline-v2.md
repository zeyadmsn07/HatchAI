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
| ASSUMPTION: university students will pay a recurring price; no verified source states a price for this kind of product | high | If fewer than 3% of landing-page visitors click a priced plan, stop or pivot pricing. | No verified price in the source ledger; No primary willingness-to-pay data (demand test NOT_RUN) |
| university students feel the problem behind S12, which describes the market, not a pain strongly enough to switch tools | high | If fewer than 5 of 10 university students describe a recent, concrete instance of it, stop. | Demand rests on one source (S12); No verified quote names a pain |
| university students will choose a focused tool over the incumbents in S13, S16 ('Apr 16, 2026 · The best study apps for university students in 2026 —…') | medium | If 7 of 10 university students say an incumbent from S13, S16 already does the job well enough, pivot to the gap the Strategist ranks first. | — |
| What S3, S4 say about local access and payment still holds for university students today ('Individuals using the Internet (% of population) for Egypt,…') | low | If no local payment method is supported by an available sandbox processor, pivot channel. | — |
| What S9, S24 say about the channel still holds for university students today ('Reach out to us for consultations on marketing strategies…') | low | If two community posts produce fewer than 100 landing-page visits, change channel. | — |

**Gate 2 recommendation:** GO
