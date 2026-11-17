"""Founder approval is enforced in code: nothing advances without a valid, allowed decision."""
import approval
import db


def _gate(run_id, outcome, token="tok", status=None):
    db.create_run(run_id, token, "{}", "2026-01-01T00:00:00Z")
    db.update_run_status(run_id, status or "gate_1_pending", phase=1)
    db.save_gate_result(run_id, 1, outcome, 60.0, 3.5, "r", {})


def test_approve_go_with_valid_token():
    _gate("a1", "go")
    assert approval.record_decision("a1", 1, "approve", "tok") == (True, "")
    assert db.get_gate_result("a1", 1)["founder_decision"] == "approve"
    entry = db.get_log_entries("a1")[-1]
    assert entry["approved_by"] == "founder" and entry["action"] == "gate_1_decision"


def test_wrong_or_missing_token_rejected():
    _gate("a2", "go", token="right")
    assert not approval.record_decision("a2", 1, "approve", "wrong")[0]
    assert not approval.record_decision("a2", 1, "approve", "")[0]


def test_cannot_decide_twice():
    _gate("a3", "go")
    assert approval.record_decision("a3", 1, "approve", "tok")[0]
    ok, err = approval.record_decision("a3", 1, "approve", "tok")
    assert not ok and "already" in err


def test_approve_not_allowed_unless_go():
    for outcome in ("repeat", "pivot", "stop"):
        _gate(f"a4{outcome}", outcome)
        ok, err = approval.record_decision(f"a4{outcome}", 1, "approve", "tok")
        assert not ok and "not allowed" in err


def test_override_requires_written_reason():
    _gate("a5", "stop")
    ok, err = approval.record_decision("a5", 1, "override_stop", "tok", override_reason=" ")
    assert not ok and "reason" in err
    assert approval.record_decision("a5", 1, "override_stop", "tok", "Founder interviewed 20 users")[0]


def test_decision_only_while_gate_pending():
    _gate("a6", "go", status="phase_2_running")
    ok, err = approval.record_decision("a6", 1, "approve", "tok")
    assert not ok and "not awaiting" in err


def test_unknown_decision_rejected():
    _gate("a7", "go")
    assert not approval.record_decision("a7", 1, "publish_everything", "tok")[0]
