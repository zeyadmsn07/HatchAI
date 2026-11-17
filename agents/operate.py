"""Operate & learn agent.

Reads stored counts only:
  * page visits, unique visitors and consented waitlist sign-ups from the generated
    MVP's own database (generated_mvps/<run>/app.db), via the MVP's own Store.metrics();
  * test-mode orders/refunds from the sale-to-cash simulation.
Applies the decision rule pre-registered in Phase 2 (thresholds read from the stored
DemandTest) to REAL traffic only. TEST traffic (labelled by the MVP) is reported in a
separate section as a pipeline check and is never used as evidence of demand.
"""
from __future__ import annotations

import importlib.util
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

import callbacks
from models import DemandTest, FounderBrief

EMPTY = {"visits": 0, "unique_visitors": 0, "signups": 0}


def decide(signups: int, visitors: int, dt: DemandTest) -> tuple[str, str]:
    """Pre-registered rule; every threshold comes from the stored DemandTest."""
    if visitors < dt.min_unique_visitors:
        return ("INSUFFICIENT_DATA",
                f"{visitors} unique visitors < {dt.min_unique_visitors} required by the pre-registered rule.")
    rate = signups / visitors
    if rate >= dt.go_signup_rate:
        return "PERSEVERE", f"sign-up rate {rate:.1%} ≥ {dt.go_signup_rate:.0%} ({signups}/{visitors})"
    if rate < dt.stop_signup_rate:
        return "STOP", f"sign-up rate {rate:.1%} < {dt.stop_signup_rate:.0%} ({signups}/{visitors})"
    return ("PIVOT", f"sign-up rate {rate:.1%} between {dt.stop_signup_rate:.0%} and "
                     f"{dt.go_signup_rate:.0%} ({signups}/{visitors})")


def read_mvp_metrics(app_dir: Path | None, db_name: str = "app.db") -> dict:
    """Stored counts from the MVP database, REAL and TEST kept apart."""
    db = Path(app_dir) / db_name if app_dir else None
    if not db or not db.exists():
        return {"real": dict(EMPTY), "test": dict(EMPTY),
                "source": "no MVP database yet (the MVP has not been run with a persistent app.db)"}
    spec = importlib.util.spec_from_file_location(f"mvp_store_{abs(hash(str(db)))}", Path(app_dir) / "store.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    store = mod.Store(str(db))
    try:
        m = store.metrics()
    finally:
        store.conn.close()
    return {**m, "source": f"{Path(app_dir).name}/{db_name} (read via the MVP's Store.metrics())"}


def run(run_id: str, brief: FounderBrief, demand_test: DemandTest, app_dir: Path | None,
        payment: dict | None = None) -> str:
    dt = demand_test
    m = read_mvp_metrics(app_dir)
    real, test = m["real"], m["test"]
    decision, why = decide(real["signups"], real["unique_visitors"], dt)
    callbacks.log(run_id=run_id, agent="operate", action="read_metrics_and_apply_preregistered_rule",
                  sources=[], model=None, cost=0, phase=6,
                  outcome=f"{decision.lower()} (real: {real['unique_visitors']} visitors, {real['signups']} sign-ups)")
    test_section = "No TEST traffic recorded."
    if test["visits"] or test["signups"]:
        t_decision, t_why = decide(test["signups"], test["unique_visitors"], dt)
        callbacks.log(run_id=run_id, agent="operate", action="pipeline_check_on_test_traffic", sources=[],
                      model=None, cost=0, phase=6, outcome=f"TEST only: {t_decision.lower()}")
        test_section = f"""| Metric | TEST value |
|---|---|
| Page visits | {test['visits']} |
| Unique visitors | {test['unique_visitors']} |
| Waitlist sign-ups (consented, @example.com) | {test['signups']} |

Rule applied to TEST data: **{t_decision}** — {t_why}.
This only proves that visits and sign-ups are recorded, stored, read back and fed through
the rule correctly. **It is not evidence of demand and is excluded from the decision above.**"""
    payment = payment or {}
    synthetic = "\n".join(f"| {s} | {v} | {decide(s, v, dt)[0]} |" for s, v in ((45, 320), (20, 400), (5, 350), (12, 90)))
    return f"""# Phase 6 — Operate & learn: {brief.idea[:80]}

## Real traffic (the only input to the decision)

| Metric | Value | Source |
|---|---|---|
| Unique visitors | {real['unique_visitors']} | {m['source']} |
| Page visits | {real['visits']} | same |
| Waitlist sign-ups (consented) | {real['signups']} | same |
| Test-mode orders (simulation) | {payment.get('orders', 0)} | sale-to-cash simulation, MOCKED |
| Test-mode refunds (simulation) | {payment.get('refunds', 0)} | sale-to-cash simulation, MOCKED |

## Pre-registered rule (stored in Phase 2)

Minimum {dt.min_unique_visitors} unique visitors; PERSEVERE if sign-up rate ≥ {dt.go_signup_rate:.0%};
STOP if < {dt.stop_signup_rate:.0%}; PIVOT in between. Channel: {dt.channel}; {dt.duration_days} days;
budget USD {dt.cost_usd}. Demand-test status: **{dt.status}**.

## Decision on real traffic: **{decision}**

{why}

## TEST traffic — pipeline check, NOT demand

{test_section}

## Next actions (each needs founder approval)

1. Approve and post the Phase 5 launch drafts in the two named communities.
2. Run the MVP with its persistent database (`python server.py --db app.db` in the generated folder).
3. Re-measure after {dt.duration_days} days: `python orchestrator.py measure <run_id>`.

## How the rule would decide — SYNTHETIC inputs (illustration only, not results)

| Sign-ups | Unique visitors | Decision |
|---|---|---|
{synthetic}
"""
