# Phase 4 — Pricing: STEM Recall

> Payments are **MOCKED** (local simulation only). Prices are a starting hypothesis for the
> demand test, not a forecast. Nothing here promises revenue.

## Evidence

Competitor monthly prices found in fetched sources (median = **USD 4.99**):

| Price | Source |
|---|---|
| $4.99/month | https://laxuai.com/blog/best-spaced-repetition-apps-2026 |

ASSUMPTION: no income data fetched for this geography — no affordability cap applied.

## Method

1. Anchor = median competitor price.
2. Entry price = 50% of anchor (new entrant discount, ASSUMPTION), capped by local affordability when known.
3. The core job stays free; paid tiers add capacity only (no core feature behind a paywall).

## Tiers

| Tier | Price (USD) | Includes |
|---|---|---|
| Free | 0 | All core features, up to the free item limit |
| Plus | 2.50 / month | Higher limits, export |
| Team / institution | 12.50 / month | 5 seats, shared content |

Target user: university students. Geography: Egypt. Local-currency display at checkout is an ASSUMPTION to verify with the chosen processor.

## Kill criterion (from Phase 2)

If fewer than 3% of demand-test visitors click the Plus tier, revisit price or value before building further.
