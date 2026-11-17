"""Smoke tests for founder approval — no pipeline action may proceed without approval."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_file
    import db
    db.init_db()
    yield db
    os.environ.pop("DB_PATH", None)


def _make_run(run_id, token):
    import db
    db.create_run(run_id, token, "{}", "2026-01-01T00:00:00Z")
    db.save_gate_result(run_id, 1, "go", 65.0, 3.8, "Strong", {"ok": True})


def test_approve_with_valid_token(isolated_db):
    import approval
    _make_run("appr-1", "valid-token-abc")
    ok, err = approval.record_decision("appr-1", 1, "approve", "valid-token-abc")
    assert ok, err


def test_approve_fails_with_wrong_token(isolated_db):
    import approval
    _make_run("appr-2", "correct-token")
    ok, err = approval.record_decision("appr-2", 1, "approve", "wrong-token")
    assert not ok
    assert "Invalid" in err


def test_cannot_double_approve(isolated_db):
    import approval
    _make_run("appr-3", "tok")
    ok1, _ = approval.record_decision("appr-3", 1, "approve", "tok")
    ok2, err2 = approval.record_decision("appr-3", 1, "approve", "tok")
    assert ok1
    assert not ok2
    assert "already" in err2.lower()


def test_override_stop_requires_reason(isolated_db):
    import db, approval
    db.create_run("appr-4", "tok", "{}", "2026-01-01T00:00:00Z")
    db.save_gate_result("appr-4", 1, "stop", 15.0, 1.0, "Weak", {})
    ok, err = approval.record_decision("appr-4", 1, "override_stop", "tok", override_reason="")
    assert not ok
    assert "reason" in err.lower()


def test_override_stop_succeeds_with_reason(isolated_db):
    import db, approval
    db.create_run("appr-5", "tok", "{}", "2026-01-01T00:00:00Z")
    db.save_gate_result("appr-5", 1, "stop", 15.0, 1.0, "Weak", {})
    ok, err = approval.record_decision("appr-5", 1, "override_stop", "tok",
                                       override_reason="Founder has inside knowledge not in sources")
    assert ok, err


def test_stop_decision_recorded(isolated_db):
    import db, approval
    _make_run("appr-6", "tok")
    ok, _ = approval.record_decision("appr-6", 1, "stop", "tok")
    assert ok
    gate = db.get_gate_result("appr-6", 1)
    assert gate["founder_decision"] == "stop"
