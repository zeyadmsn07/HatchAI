"""Smoke tests for the pipeline — offline mode, no API keys or network required."""
import sys, os, json, pathlib, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Each test gets a fresh temporary SQLite file."""
    db_file = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_file
    import db
    db.init_db()
    import payments
    payments.init_payments()
    yield db
    os.environ.pop("DB_PATH", None)


def test_db_init(isolated_db):
    assert isolated_db is not None


def test_create_and_get_run(isolated_db):
    import db
    db.create_run("test-run-1", "token123", "{}", "2026-01-01T00:00:00Z")
    run = db.get_run("test-run-1")
    assert run is not None
    assert run["run_id"] == "test-run-1"
    assert run["status"] == "created"


def test_update_run_status(isolated_db):
    import db
    db.create_run("test-run-2", "token456", "{}", "2026-01-01T00:00:00Z")
    db.update_run_status("test-run-2", "phase_1_running", phase=1)
    run = db.get_run("test-run-2")
    assert run["status"] == "phase_1_running"
    assert run["phase"] == 1


def test_save_and_get_gate_result(isolated_db):
    import db
    db.create_run("test-run-3", "token789", "{}", "2026-01-01T00:00:00Z")
    db.save_gate_result("test-run-3", 1, "go", 65.0, 3.8, "Strong evidence", {"e_ok": True})
    gate = db.get_gate_result("test-run-3", 1)
    assert gate is not None
    assert gate["outcome"] == "go"
    assert gate["evidence_score"] == 65.0


def test_log_action_and_export(isolated_db, tmp_path):
    import db
    log_path = str(tmp_path / "test_log.json")
    db.log_action("r1", "researcher", "collect_evidence", sources=["https://example.com"],
                  model="offline-mock", cost=0, phase=1)
    entries = db.get_log_entries(run_id="r1")
    assert len(entries) >= 1
    assert entries[0]["agent"] == "researcher"


def test_offline_intake_agent(isolated_db):
    import db
    db.create_run("test-intake", "tok", "{}", "2026-01-01T00:00:00Z")
    from agents.intake import run as intake_run
    brief = intake_run("test-intake", "An AI study tool for Egyptian students")
    assert brief is not None
    assert brief.idea


def test_offline_research_agent(isolated_db):
    import db
    db.create_run("test-research", "tok", "{}", "2026-01-01T00:00:00Z")
    from agents.intake import run as intake_run
    from agents.researcher import run as research_run
    brief = intake_run("test-research", "AI study planner for Egypt")
    findings = research_run("test-research", brief)
    assert findings is not None
    assert len(findings.claims) > 0


def test_offline_validator_agent(isolated_db):
    import db
    db.create_run("test-validator", "tok", "{}", "2026-01-01T00:00:00Z")
    from agents.intake import run as intake_run
    from agents.researcher import run as research_run
    from agents.validator import run_critique, run_canvas, run_demand_test
    brief = intake_run("test-validator", "AI study planner for Egypt")
    findings = research_run("test-validator", brief)
    critique = run_critique("test-validator", brief, findings)
    assert critique is not None
    canvas = run_canvas("test-validator", brief, findings, critique)
    assert canvas is not None
    dt = run_demand_test("test-validator", brief, canvas)
    assert dt.status == "NOT_RUN"


def test_payment_simulation(isolated_db):
    import payments, delivery, refunds, reconcile

    result = payments.checkout("test-pay-run", amount_egp=4900)
    assert result["order_id"]

    paid = payments.process_checkout(result["payload"], result["signature"])
    assert paid["status"] == "paid"
    assert paid["token"]

    replay = payments.process_checkout(result["payload"], result["signature"])
    assert replay["status"] == "duplicate_replay"

    refund = refunds.process_refund(result["order_id"])
    assert refund["status"] == "refunded"
    assert refund["token_revoked"] is True

    token_check = delivery.check_entitlement(paid["token"])
    assert token_check["valid"] is False
    assert token_check["reason"] == "token revoked"


def test_payment_reconciliation(isolated_db):
    import payments, refunds, reconcile

    co = payments.checkout("test-recon-run", amount_egp=4900)
    paid = payments.process_checkout(co["payload"], co["signature"])
    refund = refunds.process_refund(co["order_id"])

    result = reconcile.run_reconciliation("test-recon-run")
    assert result["pass"] is True
    assert result["mismatches"] == []
