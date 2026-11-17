"""Orchestrator — state-machine pipeline.

Phases run as background tasks; each phase ends by writing Gate results and
setting status to GATE_N_PENDING.  The founder decides via POST /api/runs/{id}/gates/{n}/decide,
which triggers the next phase.

CLI usage:
    python orchestrator.py demo          # strong idea, auto-approve all gates
    python orchestrator.py demo-stop     # weak idea, stops at Gate 1
    python orchestrator.py run <brief>   # interactive (web) run
"""
from __future__ import annotations

import json
import os
import pathlib
import secrets
import sys
import threading
import logging
from datetime import datetime, timezone

import db
import callbacks
import gates
import approval
from models import FounderBrief, RunStatus, GateOutcome

log = logging.getLogger(__name__)

OUTPUTS = pathlib.Path("outputs")
OUTPUTS.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Public API — called from app.py and CLI
# ---------------------------------------------------------------------------

def start_run(brief_text: str, run_id: str | None = None, auto_approve: bool = False) -> str:
    db.init_db()
    if run_id is None:
        run_id = secrets.token_hex(8)
    founder_token = secrets.token_hex(16)
    ts = datetime.now(timezone.utc).isoformat()
    db.create_run(run_id, founder_token, json.dumps({"raw": brief_text}), ts, auto_approve=auto_approve)
    db.update_run_status(run_id, "phase_1_running", phase=1)

    t = threading.Thread(
        target=_run_phase_1, args=(run_id, brief_text), daemon=True
    )
    t.start()
    return run_id


def advance_after_gate(run_id: str, gate_id: int, decision: str) -> None:
    """Called after the founder records a gate decision; starts the next phase."""
    _PHASE_STARTERS = {
        1: _run_phase_2,
        2: _run_phase_3,
        3: _run_phase_4,
        4: _run_phase_5,
        5: _run_phase_6,
    }
    if decision in ("approve", "override_stop", "repeat") and gate_id in _PHASE_STARTERS:
        fn = _PHASE_STARTERS[gate_id]
        t = threading.Thread(target=fn, args=(run_id,), daemon=True)
        t.start()
    elif decision == "stop":
        db.update_run_status(run_id, "stopped", error="Founder stopped the run at gate " + str(gate_id))


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------

def _run_phase_1(run_id: str, brief_text: str):
    auto_approve = _is_auto_approve(run_id)
    try:
        db.update_run_status(run_id, "phase_1_running", phase=1)

        # Guardrail 0
        blocked, reason = gates.guardrail_0(brief_text)
        if blocked:
            callbacks.log(run_id, "gate", "guardrail_0_block", phase=1, outcome="stop")
            _write(run_id, "phase1_gate_decision.md",
                   f"# Gate 1 — BLOCKED by Guardrail 0\n\n**Reason:** {reason}\n\n"
                   "This run cannot proceed. Gate 0 blocks have no override.")
            db.update_run_status(run_id, "stopped", error="Guardrail 0: " + reason)
            return

        from agents.intake import run as intake_run
        from agents.researcher import run as research_run

        # Phase 1 steps
        brief = intake_run(run_id, brief_text)
        findings = research_run(run_id, brief)

        # Compute gate
        gate_result = gates.evaluate_gate_1(findings)
        db.save_gate_result(
            run_id, 1, gate_result.outcome.value,
            gate_result.evidence_score, gate_result.viability_score,
            gate_result.reason, gate_result.checks,
        )
        callbacks.log(run_id, "gate", "gate_1_evaluation", phase=1, outcome=gate_result.outcome.value)

        # Write outputs
        _write(run_id, "phase1_step1_intake.md", _format_brief(brief))
        _write(run_id, "phase1_step2_opportunities.md", _format_findings(findings))
        _write(run_id, "phase1_step3_sources.json",
               json.dumps([s.model_dump() for s in findings.sources], indent=2))
        _write(run_id, "phase1_gate_decision.md", _format_gate(gate_result))

        # Store findings for next phase
        _store_state(run_id, "brief", brief.model_dump_json())
        _store_state(run_id, "findings", findings.model_dump_json())

        db.update_run_status(run_id, "gate_1_pending", phase=1)

        if auto_approve:
            _auto_decide(run_id, 1, gate_result.outcome, brief_text)

    except Exception as exc:
        log.exception("Phase 1 failed for run %s", run_id)
        db.update_run_status(run_id, "failed", error=str(exc))


def _run_phase_2(run_id: str):
    auto_approve = _is_auto_approve(run_id)
    try:
        db.update_run_status(run_id, "phase_2_running", phase=2)

        from agents.validator import run_critique, run_canvas, run_demand_test

        brief_json = _load_state(run_id, "brief")
        findings_json = _load_state(run_id, "findings")
        brief = FounderBrief(**json.loads(brief_json))

        from models import ResearchFindings
        findings = ResearchFindings(**json.loads(findings_json))

        critique = run_critique(run_id, brief, findings)
        canvas = run_canvas(run_id, brief, findings, critique)
        demand_test = run_demand_test(run_id, brief, canvas)

        gate_result = gates.evaluate_gate_2(findings, critique)
        db.save_gate_result(
            run_id, 2, gate_result.outcome.value,
            gate_result.evidence_score, gate_result.viability_score,
            gate_result.reason, gate_result.checks,
        )
        callbacks.log(run_id, "gate", "gate_2_evaluation", phase=2, outcome=gate_result.outcome.value)

        _write(run_id, "phase2_step1_critique.md", _format_critique(critique))
        _write(run_id, "phase2_step2_lean-canvas.md", _format_canvas(canvas))
        _write(run_id, "phase2_step3_demand-test-plan.md", _format_demand_test(demand_test))
        _write(run_id, "phase2_gate_decision.md", _format_gate(gate_result))

        _store_state(run_id, "canvas", canvas.model_dump_json())
        _store_state(run_id, "critique", critique.model_dump_json())
        _store_state(run_id, "demand_test", demand_test.model_dump_json())

        db.update_run_status(run_id, "gate_2_pending", phase=2)

        if auto_approve:
            _auto_decide(run_id, 2, gate_result.outcome)

    except Exception as exc:
        log.exception("Phase 2 failed for run %s", run_id)
        db.update_run_status(run_id, "failed", error=str(exc))


def _run_phase_3(run_id: str):
    auto_approve = _is_auto_approve(run_id)
    try:
        db.update_run_status(run_id, "phase_3_running", phase=3)

        from agents.builder import run as build_run

        brief = FounderBrief(**json.loads(_load_state(run_id, "brief")))
        from models import LeanCanvas, Critique
        canvas = LeanCanvas(**json.loads(_load_state(run_id, "canvas")))
        critique = Critique(**json.loads(_load_state(run_id, "critique")))

        artifacts = build_run(run_id, brief, canvas, critique)
        mvp_spec = artifacts["mvp_spec"]
        waitlist_html = artifacts["waitlist_html"]

        gate_result = gates.evaluate_gate_3(mvp_spec)
        db.save_gate_result(run_id, 3, gate_result.outcome.value, 0, 0, gate_result.reason, gate_result.checks)
        callbacks.log(run_id, "gate", "gate_3_evaluation", phase=3, outcome=gate_result.outcome.value)

        _write(run_id, "phase3_step1_mvp-spec.md", mvp_spec)
        _write(run_id, "phase3_step2_waitlist-preview.html", waitlist_html)
        _write(run_id, "phase3_gate_decision.md", _format_gate(gate_result))

        db.update_run_status(run_id, "gate_3_pending", phase=3)

        if auto_approve:
            _auto_decide(run_id, 3, gate_result.outcome)

    except Exception as exc:
        log.exception("Phase 3 failed for run %s", run_id)
        db.update_run_status(run_id, "failed", error=str(exc))


def _run_phase_4(run_id: str):
    auto_approve = _is_auto_approve(run_id)
    try:
        db.update_run_status(run_id, "phase_4_running", phase=4)

        from agents.commercial import run as commercial_run

        brief = FounderBrief(**json.loads(_load_state(run_id, "brief")))
        from models import LeanCanvas
        canvas = LeanCanvas(**json.loads(_load_state(run_id, "canvas")))

        result = commercial_run(run_id, brief, canvas)
        pricing = result["pricing"]
        policies = result["policies"]

        gate_result = gates.evaluate_gate_4(pricing, policies)
        db.save_gate_result(run_id, 4, gate_result.outcome.value, 0, 0, gate_result.reason, gate_result.checks)
        callbacks.log(run_id, "gate", "gate_4_evaluation", phase=4, outcome=gate_result.outcome.value)

        _write(run_id, "phase4_step1_pricing.md", pricing)
        _write(run_id, "phase4_step2_policies.md", policies)
        _write(run_id, "phase4_gate_decision.md", _format_gate(gate_result))

        db.update_run_status(run_id, "gate_4_pending", phase=4)

        if auto_approve:
            _auto_decide(run_id, 4, gate_result.outcome)

    except Exception as exc:
        log.exception("Phase 4 failed for run %s", run_id)
        db.update_run_status(run_id, "failed", error=str(exc))


def _run_phase_5(run_id: str):
    auto_approve = _is_auto_approve(run_id)
    try:
        db.update_run_status(run_id, "phase_5_running", phase=5)

        from payments import init_payments, checkout, process_checkout
        from refunds import process_refund
        from reconcile import run_reconciliation, format_payment_log

        init_payments()
        brief = FounderBrief(**json.loads(_load_state(run_id, "brief")))

        # Launch drafts (PENDING_FOUNDER_APPROVAL — never posted)
        launch_drafts = _draft_launch_copy(brief)
        _write(run_id, "phase5_step1_launch-drafts.md", launch_drafts)

        # Sale-to-Cash simulation
        co = checkout(run_id, amount_egp=4900)
        paid = process_checkout(co["payload"], co["signature"])
        replay = process_checkout(co["payload"], co["signature"])
        refund_result = process_refund(co["order_id"])
        recon = run_reconciliation(run_id)
        payment_log = format_payment_log(run_id, paid, refund_result, replay, recon)

        _write(run_id, "payment_test_log.md", payment_log)

        gate_result = gates.evaluate_gate_5(payment_log)
        db.save_gate_result(run_id, 5, gate_result.outcome.value, 0, 0, gate_result.reason, gate_result.checks)
        callbacks.log(run_id, "gate", "gate_5_evaluation", phase=5, outcome=gate_result.outcome.value)
        _write(run_id, "phase5_gate_decision.md", _format_gate(gate_result))

        callbacks.log(run_id, "payments", "sale_to_cash_simulation", phase=5)

        db.update_run_status(run_id, "gate_5_pending", phase=5)

        if auto_approve:
            _auto_decide(run_id, 5, gate_result.outcome)

    except Exception as exc:
        log.exception("Phase 5 failed for run %s", run_id)
        db.update_run_status(run_id, "failed", error=str(exc))


def _run_phase_6(run_id: str):
    try:
        db.update_run_status(run_id, "phase_6_running", phase=6)

        from agents.operate import run as operate_run
        from models import DemandTest

        brief = FounderBrief(**json.loads(_load_state(run_id, "brief")))
        demand_test = DemandTest(**json.loads(_load_state(run_id, "demand_test")))

        memo = operate_run(run_id, brief, demand_test)
        _write(run_id, "phase6_step1_operate-memo.md", memo)

        db.update_run_status(run_id, "completed", phase=6)
        callbacks.log(run_id, "orchestrator", "run_completed", phase=6, outcome="completed")

    except Exception as exc:
        log.exception("Phase 6 failed for run %s", run_id)
        db.update_run_status(run_id, "failed", error=str(exc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_auto_approve(run_id: str) -> bool:
    run = db.get_run(run_id)
    return bool(run and run.get("auto_approve"))


def _write(run_id: str, filename: str, content: str):
    path = OUTPUTS / filename
    path.write_text(content, encoding="utf-8")
    log.info("[%s] wrote %s", run_id, filename)


def _store_state(run_id: str, key: str, value: str):
    path = pathlib.Path(f".state_{run_id}_{key}.json")
    path.write_text(value, encoding="utf-8")


def _load_state(run_id: str, key: str) -> str:
    path = pathlib.Path(f".state_{run_id}_{key}.json")
    return path.read_text(encoding="utf-8")


def _auto_decide(run_id: str, gate_id: int, outcome: GateOutcome, brief_text: str = ""):
    """In demo mode, always approve (advance) regardless of REPEAT/PIVOT; only STOP halts."""
    run = db.get_run(run_id)
    if not run:
        return
    token = run["founder_token"]
    # Demo auto-approves everything except STOP
    decision = "approve"
    ok, err = approval.record_decision(run_id, gate_id, decision, token)
    if ok:
        advance_after_gate(run_id, gate_id, decision)


def _format_brief(brief: FounderBrief) -> str:
    return f"""# Phase 1 — Intake

## Normalised Brief

| Field | Value |
|---|---|
| Idea | {brief.idea} |
| Target User | {brief.target_user} |
| Geography | {brief.geography} |
| Language | {brief.language} |
| Skills | {brief.skills} |
| Budget USD | {brief.budget_usd} |
| Hours/week | {brief.hours_per_week} |
| Values | {brief.values} |
| Tech Preference | {brief.tech_preference} |

## Assumptions Added by Intake Agent

{chr(10).join(f"- {a}" for a in brief.assumptions) or "None"}
"""


def _format_findings(findings) -> str:
    claims_md = "\n".join(
        f"- **[{c.category}]** {c.text}"
        f"{' _(ASSUMPTION)_' if c.is_assumption else ' ✓ verified'}"
        for c in findings.claims
    )
    angles_md = "\n".join(f"- {a}" for a in findings.opportunity_angles)
    return f"""# Phase 1 — Research Findings

> Every market claim below cites a source or is labelled ASSUMPTION.

## Claims by Category

{claims_md}

## Opportunity Angles

{angles_md}

## Evidence Score

{findings.evidence_score} / 100 (computed after gate evaluation)

## Sources

{chr(10).join(f"- [{s.key}] [{s.title}]({s.url}) — {s.domain}" for s in findings.sources) or "No sources fetched — offline mode"}
"""


def _format_gate(gate_result) -> str:
    checks_md = "\n".join(
        f"- {'✓' if v else '✗'} {k.replace('_', ' ')}" for k, v in gate_result.checks.items()
    )
    override_note = ""
    if gate_result.founder_override:
        override_note = f"\n\n> **STOP OVERRIDDEN BY FOUNDER:** {gate_result.override_reason}"
    return f"""# Gate {gate_result.gate_id} Decision

**Outcome:** {gate_result.outcome.value.upper()}

**Evidence Score:** {gate_result.evidence_score}
**Viability Score:** {gate_result.viability_score}

**Reason:** {gate_result.reason}

## Checks

{checks_md}
{override_note}
"""


def _format_critique(critique) -> str:
    assumptions_md = "\n".join(
        f"### {a.assumption}\n- Risk: {a.risk}\n- Kill criterion: {a.kill_criterion}\n"
        f"- Evidence gaps: {', '.join(a.evidence_gaps) or 'none listed'}"
        for a in critique.riskiest_assumptions
    )
    return f"""# Phase 2 — Validation Critique

## Summary

{critique.summary}

## Scores

| Metric | Value |
|---|---|
| Evidence Score | {critique.evidence_score} |
| Viability Score | {critique.viability_score} / 5 |
| Unresolved Kill Assumptions | {critique.unresolved_kill_assumptions} |

## Demand Signal

{critique.demand_signal}

## Founder Fit

{critique.founder_fit}

## Riskiest Assumptions

{assumptions_md}

## Recommendation

**{critique.recommendation.value.upper()}**
"""


def _format_canvas(canvas) -> str:
    blocks = [
        canvas.problem, canvas.customer_segments, canvas.unique_value_proposition,
        canvas.solution, canvas.channels, canvas.revenue_streams,
        canvas.cost_structure, canvas.key_metrics, canvas.unfair_advantage,
    ]
    rows = "\n".join(
        f"| **{b.block}** | {b.content[:120]}{'...' if len(b.content) > 120 else ''} "
        f"| {'ASSUMPTION' if b.is_assumption else 'Verified'} |"
        for b in blocks
    )
    return f"""# Phase 2 — Lean Canvas

> ASSUMPTION label means no verified source backs the block content.

| Block | Content | Status |
|---|---|---|
{rows}
"""


def _format_demand_test(dt) -> str:
    return f"""# Phase 2 — Pre-Registered Demand Test

> Status: **{dt.status}** — this test has NOT been run. Simulated results are never used as evidence.

| Field | Value |
|---|---|
| Channel | {dt.channel} |
| Metric | {dt.metric} |
| Threshold | {dt.threshold} |
| Duration | {dt.duration_days} days |
| Cost (USD) | {dt.cost_usd} |
| Status | {dt.status} |
"""


def _draft_launch_copy(brief: FounderBrief) -> str:
    return f"""# Phase 5 — Launch Drafts

> **PENDING_FOUNDER_APPROVAL** — These drafts have NOT been posted anywhere.
> Nothing is published, sent, or signed without an explicit founder approve step.

## Store Listing Draft

**{brief.idea}**

{brief.target_user} can now access {brief.idea} in {brief.geography}.
Built for real people, priced fairly.

---

## Announcement Copy Draft

We're launching {brief.idea} — an {brief.idea.lower()} designed for
{brief.target_user} in {brief.geography}.

[This copy is a draft. It has not been published.]

---

*Review and edit these drafts. Approve via the dashboard before publication.*
"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

DEMO_BRIEF_STRONG = (
    "I want to build an AI-powered flashcard and spaced-repetition study tool "
    "for university students in Egypt, focused on STEM subjects. "
    "It should support Arabic and English. "
    "I have web development skills, USD 500 budget, and 10 hours per week. "
    "I value accessibility and affordable pricing."
)

DEMO_BRIEF_WEAK = (
    "An app that sells generic study notes. I don't know who the target user is "
    "or what country. No budget. No particular skills."
)


def run_demo(mode: str = "strong"):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    db.init_db()

    if mode == "stop":
        brief_text = DEMO_BRIEF_WEAK
        run_id = "demo-stop"
        print(f"[demo-stop] Starting weak-idea run -> expect Gate 1 STOP")
    else:
        brief_text = DEMO_BRIEF_STRONG
        run_id = "demo-strong"
        print(f"[demo] Starting strong-idea run -> expect all phases GO")

    # Clean up any previous demo state
    for f in pathlib.Path(".").glob(f".state_{run_id}_*.json"):
        f.unlink(missing_ok=True)

    # Remove previous demo run from DB if exists
    with db.get_conn() as conn:
        conn.execute("DELETE FROM gate_results WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM decision_log WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM runs WHERE run_id=?", (run_id,))

    founder_token = secrets.token_hex(16)
    ts = datetime.now(timezone.utc).isoformat()
    is_auto = (mode != "stop")
    db.create_run(run_id, founder_token, json.dumps({"raw": brief_text}), ts, auto_approve=is_auto)
    print(f"Founder token: {founder_token}  (not needed for auto-approve demo)")

    if mode == "stop":
        # Phase 1 only — expect STOP
        db.update_run_status(run_id, "phase_1_running", phase=1)
        _run_phase_1_weak(run_id, brief_text)
    else:
        # Full pipeline — auto-approve all gates
        db.update_run_status(run_id, "phase_1_running", phase=1)
        _run_phase_1(run_id, brief_text)

        # Wait for completion (all phases are threaded)
        import time
        for _ in range(120):
            run = db.get_run(run_id)
            status = run["status"] if run else "unknown"
            if status in ("completed", "stopped", "failed"):
                break
            time.sleep(1)
            print(f"  ... {status}")

        run = db.get_run(run_id)
        print(f"\nFinal status: {run['status'] if run else 'unknown'}")

    db.export_decision_log()
    print("decision_log.json updated.")
    print("outputs/ directory updated.")


def _run_phase_1_weak(run_id: str, brief_text: str):
    """Phase 1 for the weak-idea demo — produces STOP at Gate 1."""
    blocked, reason = gates.guardrail_0(brief_text)
    if blocked:
        _write(run_id, "phase1_gate_weak_idea.md",
               f"# Gate 1 — BLOCKED by Guardrail 0\n\n**Reason:** {reason}\n")
        db.update_run_status(run_id, "stopped")
        return

    from agents.intake import run as intake_run
    brief = intake_run(run_id, brief_text)

    # Use the weak-idea research (low evidence)
    from llm_gateway import weak_idea_research
    findings = weak_idea_research()

    gate_result = gates.evaluate_gate_1(findings)
    db.save_gate_result(
        run_id, 1, gate_result.outcome.value,
        gate_result.evidence_score, gate_result.viability_score,
        gate_result.reason, gate_result.checks,
    )
    callbacks.log(run_id, "gate", "gate_1_evaluation", phase=1, outcome=gate_result.outcome.value)

    _write(run_id, "phase1_step1_intake_weak.md", _format_brief(brief))
    _write(run_id, "phase1_gate_weak_idea.md", _format_gate(gate_result))

    db.update_run_status(run_id, "stopped")
    print(f"[demo-stop] Gate 1 outcome: {gate_result.outcome.value.upper()} — {gate_result.reason}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if mode in ("demo", "strong"):
        run_demo("strong")
    elif mode in ("demo-stop", "stop"):
        run_demo("stop")
    else:
        print("Usage: python orchestrator.py [demo|demo-stop]")
        sys.exit(1)
