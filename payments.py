"""Payment simulation — MOCKED.

No real payment processor, no sandbox API, no payment SDKs, no money held or moved.
Everything is a deterministic local simulation in SQLite.

Idempotency: a UNIQUE constraint on idempotency_key prevents double delivery.
"""
from __future__ import annotations

import hashlib
import hmac
import json
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


def init_payments():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                run_id TEXT,
                amount_minor INTEGER NOT NULL,
                currency TEXT DEFAULT 'EGP',
                status TEXT DEFAULT 'CREATED',
                idempotency_key TEXT UNIQUE,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS payment_events (
                event_id TEXT PRIMARY KEY,
                order_id TEXT,
                event_type TEXT,
                payload_json TEXT,
                processed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS entitlements (
                token TEXT PRIMARY KEY,
                order_id TEXT,
                status TEXT DEFAULT 'ACTIVE',
                issued_at TEXT,
                revoked_at TEXT
            );
        """)


MOCK_HMAC_SECRET = b"mock-hmac-secret-not-real"


def sign_event(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True).encode()
    return hmac.new(MOCK_HMAC_SECRET, body, hashlib.sha256).hexdigest()


def verify_event(payload: dict, signature: str) -> bool:
    expected = sign_event(payload)
    return hmac.compare_digest(expected, signature)


def checkout(run_id: str, amount_egp: int = 4900) -> dict:
    """Simulate a checkout.completed event."""
    import uuid
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    idempotency_key = f"ik_{hashlib.sha256(order_id.encode()).hexdigest()[:16]}"
    ts = datetime.now(timezone.utc).isoformat()

    with _conn() as conn:
        try:
            conn.execute(
                "INSERT INTO orders (order_id, run_id, amount_minor, status, idempotency_key, created_at) "
                "VALUES (?, ?, ?, 'CREATED', ?, ?)",
                (order_id, run_id, amount_egp, idempotency_key, ts),
            )
        except sqlite3.IntegrityError:
            return {"status": "duplicate", "order_id": order_id}

    payload = {"event_type": "checkout.completed", "order_id": order_id,
               "idempotency_key": idempotency_key, "amount": amount_egp}
    sig = sign_event(payload)
    return {"order_id": order_id, "idempotency_key": idempotency_key,
            "signature": sig, "payload": payload}


def process_checkout(payload: dict, signature: str) -> dict:
    """Process a signed checkout event — idempotent."""
    if not verify_event(payload, signature):
        return {"status": "error", "reason": "invalid signature"}

    ik = payload["idempotency_key"]
    order_id = payload["order_id"]
    ts = datetime.now(timezone.utc).isoformat()

    with _conn() as conn:
        existing = conn.execute(
            "SELECT * FROM payment_events WHERE event_id=?", (ik,)
        ).fetchone()
        if existing:
            # Idempotent replay — return original receipt
            ent = conn.execute(
                "SELECT token FROM entitlements WHERE order_id=?", (order_id,)
            ).fetchone()
            return {"status": "duplicate_replay", "order_id": order_id,
                    "token": ent["token"] if ent else None}

        conn.execute(
            "INSERT INTO payment_events (event_id, order_id, event_type, payload_json, processed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (ik, order_id, "checkout.completed", json.dumps(payload), ts),
        )
        conn.execute("UPDATE orders SET status='PAID' WHERE order_id=?", (order_id,))

    from delivery import issue_entitlement
    token = issue_entitlement(order_id)
    return {"status": "paid", "order_id": order_id, "token": token}
