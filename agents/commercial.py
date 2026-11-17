"""Commercial agent — evidence-anchored pricing + policy templates.

Pricing method (deterministic, every number traced):
  * competitor anchor = median monthly USD price found in fetched passages
    (each price cites its source URL); otherwise an ASSUMPTION default;
  * affordability cap = 1% of monthly GDP per capita when the World Bank
    passage for the geography was fetched (threshold itself is an ASSUMPTION);
  * the core product stays free — the paid tier adds capacity, never gates the core job.
Policies are templates labelled "not legal advice". No payment SDKs or keys.
"""
from __future__ import annotations

import os
import re
import statistics
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import callbacks
from models import FounderBrief, LeanCanvas, ResearchFindings

_PRICE = re.compile(r"\$\s?(\d{1,3}(?:\.\d{1,2})?)\s*(?:/|per|a)\s*(?:mo\b|month)", re.I)
_GDP = re.compile(r"GDP per capita \(current US\$\) for (.+?) in (\d{4}): (\d[\d,]*(?:\.\d+)?)")
DEFAULT_ANCHOR = 8.0


def price_evidence(findings: ResearchFindings) -> tuple[list[tuple[float, str]], tuple[float, str, str] | None]:
    prices, gdp = [], None
    for s in findings.sources:
        for p in s.passages:
            for m in _PRICE.finditer(p):
                v = float(m.group(1))
                if 0.5 <= v <= 100:
                    prices.append((v, s.url))
            g = _GDP.search(p)
            if g:
                gdp = (float(g.group(3).replace(",", "")), g.group(1), s.url)
    return prices, gdp


def compute_pricing(findings: ResearchFindings) -> dict:
    prices, gdp = price_evidence(findings)
    anchor = round(statistics.median(v for v, _ in prices), 2) if prices else DEFAULT_ANCHOR
    plus = round(anchor * 0.5, 2)
    cap = None
    if gdp:
        cap = round(gdp[0] / 12 * 0.01, 2)
        plus = min(plus, cap)
    plus = max(round(plus, 2), 0.99)
    return {"anchor": anchor, "anchor_sources": prices[:6], "gdp": gdp, "cap": cap, "plus": plus,
            "team": round(plus * 5, 2), "anchor_is_assumption": not prices}


def run(run_id: str, brief: FounderBrief, canvas: LeanCanvas, findings: ResearchFindings,
        product_name: str = "") -> dict:
    pr = compute_pricing(findings)
    pricing = _pricing_md(brief, pr, product_name or brief.idea[:60])
    policies = _policies_md(product_name or brief.idea[:60])
    srcs = sorted({u for _, u in pr["anchor_sources"]} | ({pr["gdp"][2]} if pr["gdp"] else set()))
    callbacks.log(run_id=run_id, agent="commercial", action="evidence_anchored_pricing", sources=srcs,
                  model=None, cost=0, phase=4)
    callbacks.log(run_id=run_id, agent="commercial", action="draft_policy_templates", sources=[],
                  model=None, cost=0, phase=4)
    return {"pricing": pricing, "policies": policies, "pricing_data": pr}


def _pricing_md(brief: FounderBrief, pr: dict, name: str) -> str:
    anchor_rows = "\n".join(f"| ${v:.2f}/month | {u} |" for v, u in pr["anchor_sources"]) or \
        f"| ${DEFAULT_ANCHOR:.2f}/month | ASSUMPTION — no competitor price found in fetched passages |"
    gdp_line = (f"World Bank: GDP per capita for {pr['gdp'][1]} = USD {pr['gdp'][0]:,.0f}/year ({pr['gdp'][2]}). "
                f"Affordability cap (ASSUMPTION: ≤ 1% of monthly GDP per capita) = **USD {pr['cap']:.2f}/month**."
                if pr["gdp"] else "ASSUMPTION: no income data fetched for this geography — no affordability cap applied.")
    return f"""# Phase 4 — Pricing: {name}

> Payments are **MOCKED** (local simulation only). Prices are a starting hypothesis for the
> demand test, not a forecast. Nothing here promises revenue.

## Evidence

Competitor monthly prices found in fetched sources (median = **USD {pr['anchor']:.2f}**{' — ASSUMPTION' if pr['anchor_is_assumption'] else ''}):

| Price | Source |
|---|---|
{anchor_rows}

{gdp_line}

## Method

1. Anchor = median competitor price.
2. Entry price = 50% of anchor (new entrant discount, ASSUMPTION), capped by local affordability when known.
3. The core job stays free; paid tiers add capacity only (no core feature behind a paywall).

## Tiers

| Tier | Price (USD) | Includes |
|---|---|---|
| Free | 0 | All core features, up to the free item limit |
| Plus | {pr['plus']:.2f} / month | Higher limits, export |
| Team / institution | {pr['team']:.2f} / month | 5 seats, shared content |

Target user: {brief.target_user}. Geography: {brief.geography}. Local-currency display at checkout is an ASSUMPTION to verify with the chosen processor.

## Kill criterion (from Phase 2)

If fewer than 3% of demand-test visitors click the Plus tier, revisit price or value before building further.
"""


def _policies_md(name: str) -> str:
    return f"""# Phase 4 — Policy templates: {name}

> **MOCKED templates — not legal advice.** Have them reviewed by a qualified lawyer before publication.
> Nothing is published or signed without an explicit founder approval.

## Terms of Service (template)

{name} ("the Service") is provided as is. You may cancel at any time. We may change or discontinue
features with notice. You may not misuse the Service or break applicable law.

## Privacy Policy (template)

We collect only what the Service needs: email (waitlist/account) and usage data. Waitlist sign-ups
require explicit consent. We do not sell personal data. Data is deleted on request or account closure.
No passwords or card numbers are stored by this system (payments would be handled by a processor).

## Refund Policy (template)

Paid plans can be cancelled at any time. Refunds for the current month are available within 7 days
of a charge. A refund revokes paid access (see `payment_test_log.md`). Refunds are issued by the
founder through the payment processor — never automatically by HatchAI.
"""
