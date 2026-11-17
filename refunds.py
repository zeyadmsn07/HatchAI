"""Refund simulation — MOCKED.

charge.refunded → revoke entitlement → update order status.
Refund before delivery means no token is ever issued.
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


def process_refund(order_id: str) -> dict:
    """Process a charge.refunded event."""
    ts = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        order = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not order:
            return {"status": "error", "reason": "order not found"}
        if order["status"] == "REFUNDED":
            return {"status": "already_refunded", "order_id": order_id}

        conn.execute(
            "UPDATE orders SET status='REFUNDED' WHERE order_id=?", (order_id,)
        )

    from delivery import revoke_entitlement
    revoked = revoke_entitlement(order_id)
    return {
        "status": "refunded",
        "order_id": order_id,
        "token_revoked": revoked,
        "refunded_at": ts,
    }
