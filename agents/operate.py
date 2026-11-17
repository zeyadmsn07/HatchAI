"""Operate & learn agent.

Reads REAL numbers only:
  * waitlist sign-ups from the generated MVP's database (generated_mvps/<run>/app.db,
    created when the founder runs the MVP);
  * test-mode orders/refunds from the sale-to-cash simulation.
Then applies the demand-test rule pre-registered in Phase 2. With no traffic yet,
the decision is INSUFFICIENT_DATA — the system never invents results. A clearly
labelled SYNTHETIC table shows how the same rule would decide on other inputs.
"""
from __future__ import annotations

import os
import sqlite3
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

import callbacks
from models import DemandTest, FounderBrief

MIN_VISITORS = 300
GO_RATE = 0.10
STOP_RATE = 0.03


def decide(signups: int, visitors: int) -> tuple[str, str]:
    """Pre-registered rule from Phase 2 (deterministic)."""
    if visitors < MIN_VISITORS:
        return "INSUFFICIENT_DATA", f"{visitors} visitors < {MIN_VISITORS} required; keep the test running."
    rate = signups / visitors
    if rate >= GO_RATE:
        return "PERSEVERE", f"sign-up rate {rate:.1%} ≥ {GO_RATE:.0%}"
    if rate < STOP_RATE:
        return "STOP", f"sign-up rate {rate:.1%} < {STOP_RATE:.0%}"
    return "PIVOT", f"sign-up rate {rate:.1%} between {STOP_RATE:.0%} and {GO_RATE:.0%}"


def read_mvp_metrics(app_dir: Path | None) -> dict:
    db = app_dir / "app.db" if app_dir else None
    if not db or not db.exists():
        return {"signups": 0, "visitors": 0, "source": "MVP not yet run by the founder (no app.db)"}
    with sqlite3.connect(db) as c:
        n = c.execute("SELECT COUNT(*) FROM events WHERE kind='waitlist'").fetchone()[0]
    return {"signups": n, "visitors": 0, "source": f"{db} (visitor analytics not implemented — STUBBED)"}


def run(run_id: str, brief: FounderBrief, demand_test: DemandTest, app_dir: Path | None,
        payment: dict | None = None) -> str:
    m = read_mvp_metrics(app_dir)
    decision, why = decide(m["signups"], m["visitors"])
    callbacks.log(run_id=run_id, agent="operate", action="read_metrics_and_apply_preregistered_rule",
                  sources=[], model=None, cost=0, phase=6, outcome=decision.lower())
    payment = payment or {}
    synthetic = "\n".join(
        f"| {s} | {v} | {decide(s, v)[0]} |" for s, v in ((45, 320), (20, 400), (5, 350), (12, 90)))
    return f"""# Phase 6 — Operate & learn: {brief.idea[:80]}

## Real data (as of this run)

| Metric | Value | Source |
|---|---|---|
| Waitlist sign-ups | {m['signups']} | {m['source']} |
| Unique visitors | {m['visitors']} | STUBBED — no analytics connector yet |
| Test-mode orders (simulation) | {payment.get('orders', 0)} | sale-to-cash simulation, MOCKED |
| Test-mode refunds (simulation) | {payment.get('refunds', 0)} | sale-to-cash simulation, MOCKED |

## Pre-registered rule (from Phase 2)

{demand_test.threshold} — channel: {demand_test.channel}; {demand_test.duration_days} days; budget USD {demand_test.cost_usd}.
Status: **{demand_test.status}**.

## Decision: **{decision}**

{why}

## Next actions (each needs founder approval)

1. Approve and post the Phase 5 launch drafts in the two named communities.
2. Run the MVP (`python server.py` in the generated folder) so sign-ups are recorded in `app.db`.
3. Re-run Phase 6 after {demand_test.duration_days} days; the rule above decides PERSEVERE / PIVOT / STOP.

## How the rule would decide — SYNTHETIC inputs (illustration only, not results)

| Sign-ups | Visitors | Decision |
|---|---|---|
{synthetic}
"""
