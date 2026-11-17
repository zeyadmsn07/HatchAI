# Phase 4 — Pricing: Narrow Recall

> Evidence mode: REPLAY of evidence_snapshots/strong_v2_scenario.json (captured 2026-11-17T20:51:46+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v2 (relevance: brief-specific user / problem / local terms)

> Payments are **MOCKED** (local simulation only). Prices are a starting hypothesis for the
> demand test, not a forecast. Nothing here promises revenue.

## Evidence

Competitor monthly prices found in fetched sources (median = **USD 8.00** — ASSUMPTION):

| Price | Source |
|---|---|
| $8.00/month | ASSUMPTION — no competitor price found in fetched passages |

World Bank: GDP per capita for Egypt, Arab Rep. = USD 3,086/year (https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=EG). Affordability cap (ASSUMPTION: ≤ 1% of monthly GDP per capita) = **USD 2.57/month**.

## Method

1. Anchor = median competitor price.
2. Entry price = 50% of anchor (new entrant discount, ASSUMPTION), capped by local affordability when known.
3. The core job stays free; paid tiers add capacity only (no core feature behind a paywall).

## Tiers

| Tier | Price (USD) | Includes |
|---|---|---|
| Free | 0 | All core features, up to the free item limit |
| Plus | 2.57 / month | Higher limits, export |
| Team / institution | 12.85 / month | 5 seats, shared content |

Target user: university students. Geography: Egypt. Local-currency display at checkout is an ASSUMPTION to verify with the chosen processor.

## Kill criterion (from Phase 2)

If fewer than 3% of demand-test visitors click the Plus tier, revisit price or value before building further.
