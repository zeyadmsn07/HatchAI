"""Founder approval store — enforced in code.

Every phase transition requires a founder decision recorded here with the
run's founder token. Agents have no access to this module.

Allowed decisions per gate outcome (computed by gates.py):
  GO      approve | stop
  REPEAT  repeat  | stop | override_stop (proceed anyway; written reason required)
  PIVOT   pivot   | stop | override_stop (proceed anyway; written reason required)
  STOP    stop    | override_stop (proceed anyway; written reason required)

Guardrail 0 blocks never create a gate record, so they cannot be overridden.
"""
from __future__ import annotations

import secrets

import db

ALLOWED = {
    "go": {"approve", "stop"},
    "repeat": {"repeat", "stop", "override_stop"},
    "pivot": {"pivot", "stop", "override_stop"},
    "stop": {"stop", "override_stop"},
}
ALL_DECISIONS = {"approve", "stop", "repeat", "pivot", "override_stop"}


def generate_token(run_id: str) -> str:
    return secrets.token_hex(16)


def verify_token(run_id: str, token: str) -> bool:
    run = db.get_run(run_id)
    if not run or not token:
        return False
    return secrets.compare_digest(run["founder_token"], token)


def record_decision(run_id: str, gate_id: int, decision: str, token: str,
                    override_reason: str = "", via: str = "founder") -> tuple[bool, str]:
    """Record a founder gate decision. Returns (success, error_message)."""
    if decision not in ALL_DECISIONS:
        return False, f"Unknown decision '{decision}'."
    if not verify_token(run_id, token):
        return False, "Invalid founder token."

    gate = db.get_gate_result(run_id, gate_id)
    if not gate:
        return False, f"Gate {gate_id} result not found for run {run_id}."
    if gate.get("founder_decision"):
        return False, "Decision already recorded for this gate."
    run = db.get_run(run_id)
    if run and run["status"] != f"gate_{gate_id}_pending":
        return False, f"Gate {gate_id} is not awaiting a decision (run status: {run['status']})."

    outcome = gate["outcome"]
    if decision not in ALLOWED.get(outcome, set()):
        hint = " Use override_stop with a written reason." if outcome == "stop" else ""
        return False, (f"'{decision}' is not allowed when the gate recommends {outcome.upper()} "
                       f"(allowed: {sorted(ALLOWED.get(outcome, set()))}).{hint}")
    if decision == "override_stop" and not override_reason.strip():
        return False, "A written reason is required to proceed against the gate's recommendation."

    db.record_gate_decision(run_id, gate_id, decision, override_reason)
    db.log_action(run_id=run_id, agent="founder", action=f"gate_{gate_id}_decision", sources=[],
                  model=None, cost=0, approved_by="founder", phase=gate_id,
                  outcome=decision if via == "founder" else f"{decision} ({via})")
    return True, ""


def get_decision(run_id: str, gate_id: int) -> dict | None:
    return db.get_gate_result(run_id, gate_id)
