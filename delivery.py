"""Delivery simulation — MOCKED.

Issues entitlements (access tokens) on successful payment.
Tokens are invalidated on refund — revocation is enforced.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "hatchai.db")


def _db_path():
    return os.environ.get("DB_PATH", DB_PATH)


def _conn():
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def issue_entitlement(order_id: str) -> str:
    """Issue a single access token for the order. Idempotent."""
    with _conn() as conn:
        existing = conn.execute(
            "SELECT token FROM entitlements WHERE order_id=?", (order_id,)
        ).fetchone()
        if existing:
            return existing["token"]

        token = secrets.token_urlsafe(24)
        ts = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO entitlements (token, order_id, status, issued_at) VALUES (?, ?, 'ACTIVE', ?)",
            (token, order_id, ts),
        )
        return token


def revoke_entitlement(order_id: str) -> bool:
    ts = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            "UPDATE entitlements SET status='REVOKED', revoked_at=? WHERE order_id=? AND status='ACTIVE'",
            (ts, order_id),
        ).rowcount
        return rows > 0


def check_entitlement(token: str) -> dict:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM entitlements WHERE token=?", (token,)).fetchone()
        if not row:
            return {"valid": False, "reason": "token not found"}
        if row["status"] == "REVOKED":
            return {"valid": False, "reason": "token revoked"}
        return {"valid": True, "order_id": row["order_id"], "issued_at": row["issued_at"]}
