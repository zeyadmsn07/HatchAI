"""Founder approval store.

Every consequential gate transition requires a matching approval record.
The founder token is printed at startup; decisions arrive only via the API
or CLI.  Gate 0 blocks have NO override path.
"""
from __future__ import annotations

import hashlib
import os
import secrets

import db


def generate_token(run_id: str) -> str:
    """Create and persist a founder token for a run."""
    token = secrets.token_hex(16)
    return token


def verify_token(run_id: str, token: str) -> bool:
    run = db.get_run(run_id)
    if not run:
        return False
    return secrets.compare_digest(run["founder_token"], token)


def record_decision(run_id: str, gate_id: int, decision: str, token: str,
                    override_reason: str = "") -> tuple[bool, str]:
    """Record a founder gate decision.

    decision must be one of: "approve", "stop", "override_stop".
    Returns (success, error_message).
    """
    if not verify_token(run_id, token):
        return False, "Invalid founder token."

    gate = db.get_gate_result(run_id, gate_id)
    if not gate:
        return False, f"Gate {gate_id} result not found for run {run_id}."

    if gate.get("founder_decision"):
        return False, "Decision already recorded for this gate."

    if decision == "override_stop":
        if gate["outcome"] != "stop":
            return False, "override_stop is only valid when the gate recommends STOP."
        if not override_reason.strip():
            return False, "A written reason is required to override a STOP recommendation."

    db.record_gate_decision(run_id, gate_id, decision, override_reason)

    # Log with approved_by = "founder"
    db.log_action(
        run_id=run_id,
        agent="founder",
        action=f"gate_{gate_id}_decision",
        sources=[],
        model=None,
        cost=0,
        approved_by="founder",
        phase=gate_id,
        outcome=decision,
    )
    return True, ""


def get_decision(run_id: str, gate_id: int) -> dict | None:
    return db.get_gate_result(run_id, gate_id)
