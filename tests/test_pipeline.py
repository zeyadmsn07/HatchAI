"""End-to-end pipeline smoke tests (offline: fixture evidence, no LLM, no network)."""
import json

import pytest
from tests.conftest import STRONG, FakeCollector

import db
import evidence
import orchestrator
import payments
import refunds
import delivery
import reconcile
from agents.intake import parse_brief

STRONG_BRIEF = orchestrator.DEMO_BRIEF_STRONG
WEAK_BRIEF = orchestrator.DEMO_BRIEF_WEAK
REQUIRED_KEYS = {"timestamp", "agent", "action", "sources", "model", "cost", "approved_by"}


def _gates(run_id):
    return [h["outcome"] for h in orchestrator._counters(run_id)["history"]]


def test_intake_marks_unstated_fields_unknown():
    b = parse_brief(WEAK_BRIEF)
    assert {"target_user", "geography", "skills"} <= set(b.unknown_fields)
    s = parse_brief(STRONG_BRIEF)
    assert (s.geography, s.budget_usd, s.hours_per_week) == ("Egypt", 500.0, 10.0)
    assert s.unknown_fields == []


def test_full_run_reaches_phase_6_with_founder_approvals(strong_collector):
    run = orchestrator.run_sync(STRONG_BRIEF, "e2e-strong", auto=True)
    assert run["status"] == "completed", run["error"]
    assert _gates("e2e-strong") == ["go"] * 5
    names = {p.name for p in orchestrator.list_outputs("e2e-strong")}
    for n in ("phase1_step2_research-findings.md", "phase2_step1_critique.md", "phase3_step1_mvp-spec.md",
              "phase3_step3_mvp-test-report.txt", "phase4_step1_pricing.md", "payment_test_log.md",
              "phase6_step1_operate-memo.md", "phase1_gate_decision.md", "phase5_gate_decision.md"):
        assert n in names, n
    report = (orchestrator.out_dir("e2e-strong") / "phase3_step3_mvp-test-report.txt").read_text(encoding="utf-8")
    assert "failures=0 errors=0 ok=True" in report
    entries = db.get_log_entries("e2e-strong", limit=500)
    decisions = [e for e in entries if e["action"].endswith("_decision")]
    assert len(decisions) == 5 and all(e["approved_by"] == "founder" for e in decisions)
    pricing = (orchestrator.out_dir("e2e-strong") / "phase4_step1_pricing.md").read_text(encoding="utf-8")
    assert "$4.99/month" in pricing and "pricing.example.net" in pricing   # price traced to its source


def test_nothing_advances_without_founder_decision(strong_collector):
    run = orchestrator.run_sync(STRONG_BRIEF, "e2e-wait", auto=False, interactive=False)
    assert run["status"] == "gate_1_pending"
    assert db.get_gate_result("e2e-wait", 2) is None
    assert not orchestrator._state_path("e2e-wait", "critique").exists()


def test_weak_idea_is_stopped_at_gate_1(strong_collector):
    run = orchestrator.run_sync(WEAK_BRIEF, "e2e-weak", auto=True)
    assert run["status"] == "stopped"
    assert _gates("e2e-weak") == ["stop"]
    assert db.get_gate_result("e2e-weak", 2) is None


def test_repeat_runs_a_second_research_round(monkeypatch):
    thin = {"demand": STRONG["demand"]}
    fc = FakeCollector([thin, STRONG])
    monkeypatch.setattr(evidence, "collect", fc)
    orchestrator.run_sync(STRONG_BRIEF, "e2e-repeat", auto=True)
    assert _gates("e2e-repeat")[:2] == ["repeat", "go"]
    assert [r for _, r in fc.calls][:2] == [1, 2]


def test_pivot_restarts_discovery_on_new_angle(monkeypatch):
    thin = {"demand": STRONG["demand"], "competitors": STRONG["competitors"]}
    fc = FakeCollector([thin, thin])
    monkeypatch.setattr(evidence, "collect", fc)
    run = orchestrator.run_sync(STRONG_BRIEF, "e2e-pivot", auto=True)
    g = _gates("e2e-pivot")
    assert g[:3] == ["repeat", "pivot", "repeat"] and g[-1] == "stop"
    assert run["status"] == "stopped"
    assert fc.calls[2][0] != fc.calls[0][0]          # research re-ran on the pivoted idea


def test_unsupported_idea_stops_at_gate_3_without_claiming_an_mvp(strong_collector):
    brief = ("An AI tutor chatbot for high-school math students in Egypt. I have web development skills, "
             "USD 300 budget, 10 hours per week.")
    run = orchestrator.run_sync(brief, "e2e-unsupported", auto=True)
    assert _gates("e2e-unsupported") == ["go", "go", "stop"]
    assert run["status"] == "stopped"
    names = {p.name for p in orchestrator.list_outputs("e2e-unsupported")}
    assert "phase3_step2_mvp-source.md" not in names and "phase3_step3_mvp-test-report.txt" not in names
    spec = (orchestrator.out_dir("e2e-unsupported") / "phase3_step1_mvp-spec.md").read_text(encoding="utf-8")
    assert spec.startswith("# Phase 3 — UNSUPPORTED: no MVP was built")
    assert "No code was generated" in spec
    gate = (orchestrator.out_dir("e2e-unsupported") / "phase3_gate_decision.md").read_text(encoding="utf-8")
    assert "STOP: no MVP was built" in gate
    app_state = orchestrator._load("e2e-unsupported", "app")
    assert app_state["supported"] is False and "No tested template fits" in app_state["reason"]
    assert "app_dir" not in app_state
    actions = [e["action"] for e in db.get_log_entries("e2e-unsupported", limit=500)]
    assert "select_template" in actions and not any(a.startswith("generate_mvp_code") for a in actions)


def test_override_after_unsupported_continues_without_mvp(strong_collector):
    brief = ("An AI tutor chatbot for high-school math students in Egypt. I have web development skills, "
             "USD 300 budget, 10 hours per week.")
    orchestrator.run_sync(brief, "e2e-unsup-ovr", auto=False, interactive=False)
    import approval
    for gid in (1, 2):
        tok = db.get_run("e2e-unsup-ovr")["founder_token"]
        orchestrator._mode.sync = True
        try:
            assert approval.record_decision("e2e-unsup-ovr", gid, "approve", tok)[0]
            orchestrator.advance_after_gate("e2e-unsup-ovr", gid, "approve")
        finally:
            orchestrator._mode.sync = False
    assert db.get_run("e2e-unsup-ovr")["status"] == "gate_3_pending"
    tok = db.get_run("e2e-unsup-ovr")["founder_token"]
    assert not approval.record_decision("e2e-unsup-ovr", 3, "approve", tok)[0]      # cannot approve a STOP
    orchestrator._mode.sync = True
    try:
        assert approval.record_decision("e2e-unsup-ovr", 3, "override_stop", tok, "I will build it in Bubble")[0]
        orchestrator.advance_after_gate("e2e-unsup-ovr", 3, "override_stop")
    finally:
        orchestrator._mode.sync = False
    assert db.get_run("e2e-unsup-ovr")["status"] == "gate_4_pending"     # Phase 4 ran with no MVP


def test_guardrail_blocks_before_any_research(strong_collector):
    run = orchestrator.run_sync("A platform selling physical goods in Egypt for students", "e2e-block", auto=True)
    assert run["status"] == "stopped" and "Guardrail 0" in run["error"]
    assert strong_collector.calls == []


def test_decision_log_export_has_required_keys(strong_collector, tmp_path):
    orchestrator.run_sync(WEAK_BRIEF, "e2e-log", auto=True)
    path = tmp_path / "log.json"
    entries = db.export_decision_log(str(path), run_ids=["e2e-log"])
    assert entries and all(REQUIRED_KEYS <= set(e) for e in entries)
    assert json.loads(path.read_text(encoding="utf-8")) == entries


def test_sale_to_cash_idempotency_revocation_reconciliation():
    co = payments.checkout("pay-run", amount_egp=250)
    paid = payments.process_checkout(co["payload"], co["signature"])
    assert paid["status"] == "paid" and paid["token"]
    assert payments.process_checkout(co["payload"], co["signature"])["status"] == "duplicate_replay"
    assert payments.process_checkout(co["payload"], "forged-signature")["status"] == "error"
    assert refunds.process_refund(co["order_id"])["token_revoked"] is True
    assert delivery.check_entitlement(paid["token"]) == {"valid": False, "reason": "token revoked"}
    assert reconcile.run_reconciliation("pay-run")["pass"] is True
