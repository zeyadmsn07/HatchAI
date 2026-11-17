"""Operate agent — MOCKED.

Generates SYNTHETIC post-launch metrics and compares them to pre-registered
thresholds. All data is clearly labelled SYNTHETIC and must never be
presented as real results.
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from models import FounderBrief, DemandTest
import callbacks


def run(run_id: str, brief: FounderBrief, demand_test: DemandTest) -> str:
    memo = _generate_memo(brief, demand_test)
    callbacks.log(
        run_id=run_id,
        agent="operate",
        action="generate_operate_memo",
        sources=[],
        model="offline-mock",
        cost=0,
        phase=6,
    )
    return memo


def _generate_memo(brief: FounderBrief, demand_test: DemandTest) -> str:
    # Fixed seed so the SYNTHETIC numbers are reproducible
    rng = random.Random(42)

    # Synthetic funnel
    impressions = rng.randint(800, 1200)
    clicks = rng.randint(60, 120)
    sign_ups = rng.randint(15, 40)
    paid = rng.randint(2, 8)
    refunds = rng.randint(0, 2)
    day7_retention = round(rng.uniform(0.25, 0.45), 2)
    mrr = paid * 49  # EGP (Student tier)

    threshold_num = 50  # from demand_test threshold text

    persevere = sign_ups >= threshold_num
    decision = "PERSEVERE" if persevere else "PIVOT or STOP"
    decision_reason = (
        f"Sign-ups ({sign_ups}) {'met' if persevere else 'did not meet'} "
        f"the pre-registered threshold of {threshold_num}."
    )

    return f"""# Operate & Learn Memo — {brief.idea}

> **MOCKED** — All metrics below are **SYNTHETIC** (seed=42).
> They demonstrate decision logic only and must not be presented as real results.

## SYNTHETIC Funnel (Week 1)

| Metric | Value |
|---|---|
| Ad impressions | {impressions} |
| Click-throughs | {clicks} |
| Waitlist sign-ups | {sign_ups} |
| Converted to paid | {paid} |
| Refunds | {refunds} |
| Day-7 retention | {day7_retention:.0%} |
| Monthly recurring revenue | EGP {mrr} |

## Pre-registered Threshold Comparison

**Test:** {demand_test.metric}
**Pre-registered threshold:** {demand_test.threshold}
**Result:** {sign_ups} sign-ups in {demand_test.duration_days} days (SYNTHETIC)

## Decision

**{decision}**

{decision_reason}

Day-7 retention of {day7_retention:.0%} is {'above' if day7_retention >= 0.30 else 'below'}
the 30% minimum viable retention threshold (ASSUMPTION).

## Recommended Actions

{'1. Invest in content marketing and referral programme.\n2. Expand to second geography.\n3. Test annual pricing.' if persevere else '1. Conduct 10 user interviews to understand drop-off.\n2. Revise value proposition.\n3. Consider pivot to B2B channel.'}

---
*All numbers are SYNTHETIC. Run a real demand test before making business decisions.*
"""
