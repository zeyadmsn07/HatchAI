# Phase 2 — Red-team critique

> Evidence mode: REPLAY of evidence_snapshots/strong_scenario.json (captured 2026-11-17T15:52:54+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

## Summary

5/5 evidence categories have verified, quoted sources (demand, competitors, pricing, local_constraints, channels). Gaps: none. Willingness to pay is untested until the pre-registered demand test runs.

## Viability score (computed by code): 4.5 / 5

| Component | Points |
|---|---|
| base | 1.0 |
| demand verified | 1.0 |
| competitors verified | 0.5 |
| pricing verified | 0.5 |
| local constraints verified | 0.5 |
| founder skills | 0.5 |
| founder time | 0.25 |
| risks testable | 0.25 |
| demand test passed | 0.0 |

## Demand signal

Memdora: Designing Cognitively-Grounded Flashcard ... reports: "This preparation burden is so significant that it deters sustained adoption: a recent study of AI flashcard systems found that students  [S6] | Active Recall & Spaced Repetition: Evidence & Effectiveness reports: "Retention Improvement Comparative research from Johns Hopkins University demonstrated that students using AI-optimized spaced repe [S7]

## Founder fit

Skills: web development; 10.0 h/week; budget USD 500.0. Founder-fit points: 0.75

## Riskiest assumptions and kill criteria

| Assumption | Risk | Kill criterion | Evidence gaps |
|---|---|---|---|
| university students will pay a recurring price in the USD 4.99–20/month range that S9, S13, S15 quote; those are competitor or vendor prices, not what this segment has agreed to pay | high | If fewer than 3 of 10 university students accept the entry price when asked directly, or fewer than 3% of landing-page visitors click a priced plan, stop or re-price. | No primary willingness-to-pay data (demand test NOT_RUN) |
| university students feel the pain S6 names ('this preparation burden is so significant that it deters sustained…') strongly enough to switch tools | medium | If fewer than 5 of 10 university students describe a recent, concrete instance of it, stop. | — |
| university students will choose a focused tool over the incumbents in S9, S11 ('Jul 29, 2026 · Compare the best flashcard apps for university…') | medium | If 7 of 10 university students say an incumbent from S9, S11 already does the job well enough, pivot to the gap the Strategist ranks first. | — |
| What S3, S4 say about local access and payment still holds for university students today ('Individuals using the Internet (% of population) for Egypt,…') | low | If no local payment method is supported by an available sandbox processor, pivot channel. | — |
| What S13, S19 say about the channel still holds for university students today ('Oct 23, 2026 · Whether you work at a 2-year or 4-year…') | low | If two community posts produce fewer than 100 landing-page visits, change channel. | — |

**Gate 2 recommendation:** GO
