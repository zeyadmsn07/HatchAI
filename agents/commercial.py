"""Commercial agent — MOCKED.

Generates pricing tiers and policy templates.
No payment SDKs, no payment keys, no real transactions.
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import FounderBrief, LeanCanvas
import callbacks


def run(run_id: str, brief: FounderBrief, canvas: LeanCanvas) -> dict:
    """Return {'pricing': str, 'policies': str}."""
    pricing = _build_pricing(brief, canvas)
    policies = _build_policies(brief)

    callbacks.log(
        run_id=run_id,
        agent="commercial",
        action="generate_pricing_and_policies",
        sources=[],
        model="offline-mock",
        cost=0,
        phase=4,
    )
    return {"pricing": pricing, "policies": policies}


def _build_pricing(brief: FounderBrief, canvas: LeanCanvas) -> str:
    geo = brief.geography.replace("ASSUMPTION: ", "")
    return f"""# Pricing — {brief.idea}

> **MOCKED** — All prices are ASSUMPTIONS based on market estimates. No payment integration exists.

## Price-to-Income Sanity Check

ASSUMPTION: Local monthly income per capita for {geo} ≈ EGP 3,000–5,000 (USD 60–100).
Pricing should not exceed 3–5% of monthly income for accessibility.

## Tiers

| Tier | Price | Features |
|---|---|---|
| Free | EGP 0 / month | Core feature, 20 items/day limit |
| Student | EGP 49 / month (~USD 1) | Unlimited items, shared decks |
| Pro | EGP 99 / month (~USD 2) | All features, priority support |

> ASSUMPTION: Competitor benchmarks suggest EGP 50–200/month is market rate.
> ASSUMPTION: Student tier at EGP 49 is below 2% of median monthly income.

## Currency

Primary currency: Egyptian Pound (EGP). USD pricing shown for reference only.

## Payments (MOCKED)

No live payment processor is configured. See `payment_test_log.md` for the
local simulation of the checkout → delivery → refund flow.
"""


def _build_policies(brief: FounderBrief) -> str:
    return f"""# Legal Policy Templates — {brief.idea}

> **MOCKED** — These are template documents only.
> **Have them reviewed by a qualified lawyer before publication. This is not legal advice.**

---

## Terms of Service

**{brief.idea}** ("the Service") is provided by the founding team.

By using the Service you agree to these terms. The Service is provided "as is"
without warranties of any kind. We reserve the right to modify or discontinue
the Service at any time.

**Prohibited uses:** You may not use the Service to distribute harmful content,
violate applicable laws, or attempt to reverse-engineer the Service.

---

## Privacy Policy

We collect only the information necessary to provide the Service (email address
and usage data). We do not sell your data to third parties. Data is stored
securely and deleted on account closure.

This policy will be updated before launch to comply with applicable data
protection law (Egypt PDPL / GDPR where applicable). — ASSUMPTION

---

## Refund Policy

Paid subscriptions may be cancelled at any time. Refunds are issued for unused
full months if requested within 7 days of charge. Partial months are not
refunded. Contact support to initiate a refund.

**Note:** No real payment processing is active. See `payment_test_log.md`.
"""
