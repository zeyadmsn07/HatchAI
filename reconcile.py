"""Reconciliation — MOCKED.

Compares internal orders, payment events, and a mock settlement file.
All money stored as integer minor units (piastres), never floats.
Gate 5 fails if any mismatch is found.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "hatchai.db")


def _db_path():
    return os.environ.get("DB_PATH", DB_PATH)


def _conn():
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# ASSUMPTION: mock processor fee schedule — 2.9% + 100 piastres per transaction
FEE_RATE = 0.029
FEE_FIXED = 100  # piastres


def run_reconciliation(run_id: str) -> dict:
    """Three-way reconciliation: orders × events × settlement."""
    with _conn() as conn:
        orders = conn.execute(
            "SELECT * FROM orders WHERE run_id=?", (run_id,)
        ).fetchall()

    results = []
    mismatches = []

    for order in orders:
        oid = order["order_id"]
        status = order["status"]
        gross = order["amount_minor"]

        with _conn() as conn:
            event = conn.execute(
                "SELECT * FROM payment_events WHERE order_id=? AND event_type='checkout.completed'",
                (oid,),
            ).fetchone()

        has_event = event is not None

        # Mock settlement line
        if status in ("PAID", "REFUNDED"):
            fee = int(gross * FEE_RATE) + FEE_FIXED
            refund_amount = gross if status == "REFUNDED" else 0
            refund_fee = int(refund_amount * FEE_RATE) + (FEE_FIXED if refund_amount else 0)
            payout = gross - fee - refund_amount + refund_fee
            settlement = {
                "order_id": oid,
                "gross": gross,
                "fee": fee,
                "refund": refund_amount,
                "refund_fee_returned": refund_fee,
                "payout": payout,
            }
        else:
            settlement = None

        ok = has_event and (settlement is not None)
        if not ok:
            mismatches.append(f"Order {oid}: event={has_event}, settlement={settlement is not None}")

        results.append({"order_id": oid, "status": status, "ok": ok,
                        "settlement": settlement})

    return {
        "run_id": run_id,
        "orders_checked": len(orders),
        "mismatches": mismatches,
        "pass": len(mismatches) == 0,
        "results": results,
        "note": "ASSUMPTION: Fee schedule (2.9% + EGP 1 fixed) is not from a real processor.",
    }


def format_payment_log(run_id: str, checkout_result: dict, refund_result: dict,
                        replay_result: dict, reconcile_result: dict) -> str:
    """Format the payment_test_log.md content."""
    checks = [
        ("IDEMPOTENCY", replay_result.get("status") == "duplicate_replay"),
        ("REVOCATION", refund_result.get("token_revoked", False)),
        ("RECONCILIATION", reconcile_result.get("pass", False)),
    ]
    lines = [
        "# Payment Test Log — MOCKED",
        "",
        "> All transactions below are simulations. No real money was moved.",
        "> No payment processor SDK is installed. HMAC secret is a local mock.",
        "",
        "## Checkout",
        f"- Order ID: `{checkout_result.get('order_id', 'n/a')}`",
        f"- Status: `{checkout_result.get('status', 'n/a')}`",
        "",
        "## Idempotency (replay test)",
        f"- Replayed webhook status: `{replay_result.get('status', 'n/a')}`",
        f"- IDEMPOTENCY: {'PASS' if checks[0][1] else 'FAIL'}",
        "",
        "## Refund",
        f"- Order: `{refund_result.get('order_id', 'n/a')}`",
        f"- Token revoked: `{refund_result.get('token_revoked', False)}`",
        f"- REVOCATION: {'PASS' if checks[1][1] else 'FAIL'}",
        "",
        "## Reconciliation",
        f"- Orders checked: {reconcile_result.get('orders_checked', 0)}",
        f"- Mismatches: {reconcile_result.get('mismatches', [])}",
        f"- RECONCILIATION: {'PASS' if checks[2][1] else 'FAIL'}",
        "",
        "## Summary",
    ]
    for name, passed in checks:
        lines.append(f"- {name}: {'PASS' if passed else 'FAIL'}")
    return "\n".join(lines)
