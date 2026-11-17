"""Orchestrator — persisted state machine for the six phases.

Each phase ends by computing its gate (gates.py, deterministic) and setting the
run to GATE_N_PENDING. Nothing advances until a founder decision is recorded
through approval.record_decision (web UI, API, or CLI prompt):

  approve        GO       -> next phase
  repeat         REPEAT   -> gate 1/2: another, broader research round; gate 3: rebuild
  pivot          PIVOT    -> restart Phase 1 on the suggested angle (Guardrail 0 re-checked)
  override_stop  any non-GO, written reason required -> next phase
  stop           any      -> run stopped

CLI:
  python orchestrator.py demo                 # committed demo: replays strong (GO), weak (STOP), REPEAT -> GO
  python orchestrator.py demo --live          # same, but strong and weak do fresh live research
  python orchestrator.py run "<brief>"        # interactive: you approve each gate at the prompt
  python orchestrator.py run "<brief>" --yes  # follow every gate recommendation automatically
  python orchestrator.py measure <run_id>     # re-run Phase 6 on the MVP's stored counts
  python orchestrator.py capture "<brief>" <snapshot.json>   # live run, save collected evidence
  python orchestrator.py replay <snapshot.json> [run_id] [--scoring v1|v2]
                                              # reproduce a run from a snapshot (no network); default: the
                                              # snapshot's own scoring version (committed snapshots: v1)
"""
from __future__ import annotations

import json
import logging
import pathlib
import secrets
import sys
import threading
from datetime import datetime, timezone

import approval
import callbacks
import db
import gates
from models import (Critique, DemandTest, FounderBrief, GateOutcome, GateResult, LeanCanvas,
                    ResearchFindings)

log = logging.getLogger(__name__)

ROOT = pathlib.Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
RUNS = ROOT / "runs"
# Demo runs write to the committed outputs/ folder; the suffix keeps scenarios apart.
DEMO_RUNS = {"demo-strong": "", "demo-weak": "-weak-idea", "demo-replay": "-replay-scenario",
             # the same three snapshots replayed under scoring v2 (separate, labelled output files)
             "demo-strong-v2": "-scoring-v2", "demo-weak-v2": "-weak-idea-scoring-v2",
             "demo-replay-v2": "-replay-scenario-scoring-v2",
             # headline: the strong brief re-captured LIVE under scoring v2 (REPEAT -> PIVOT -> GO)
             "demo-headline": "-headline-v2"}
# Committed evidence snapshot for the reproducible REPEAT/PIVOT scenario (captured from a live run).
SNAPSHOTS = ROOT / "evidence_snapshots"
DEMO_SNAPSHOT = SNAPSHOTS / "repeat_scenario.json"

_mode = threading.local()
NEXT_PHASE = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}


# ---------------------------------------------------------------------------
# Paths and state
# ---------------------------------------------------------------------------

def out_dir(run_id: str) -> pathlib.Path:
    d = OUTPUTS if run_id in DEMO_RUNS else RUNS / run_id / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def out_name(run_id: str, filename: str) -> str:
    suffix = DEMO_RUNS.get(run_id, "")
    if not suffix:
        return filename
    stem, _, ext = filename.rpartition(".")
    return f"{stem}{suffix}.{ext}"


def _record_llm_mode(run_id: str) -> None:
    """Probe once at run start and log the run's LLM mode (model name only if one is served)."""
    import llm_gateway as g
    mode = g.current_mode()
    p = g.probe() if mode != g.LLM_DISABLED else None
    st = {"mode_at_start": mode, "model": p.model if p and p.reachable else None,
          "base_url": p.base_url if p and p.reachable else None,
          "error": "" if mode == g.LLM_LIVE else (p.error if p else "HATCHAI_NO_LLM=1"), "tasks": []}
    _store(run_id, "llm", st)
    callbacks.log(run_id, "orchestrator", "llm_mode_at_start", model=st["model"], phase=0,
                  outcome=f"{mode}" + (f": {st['error']}" if st["error"] else f": {st['model']} at {st['base_url']}"))


def evidence_label(run_id: str) -> str:
    """One-line evidence-mode label for every output and log of a run."""
    ecfg = _load(run_id, "evidence_config", default=None) or {"mode": "live"}
    if ecfg.get("mode") == "replay":
        snap = load_snapshot(ecfg["snapshot"])
        return (f"REPLAY of {snap['_file']} (captured {snap['captured_at']}); "
                "no evidence was collected in this run")
    return "live (evidence collected by this run)"


def llm_label(run_id: str) -> str:
    """Run-level LLM mode: LLM_DISABLED | LLM_LIVE | LLM_UNAVAILABLE_FALLBACK, with model and per-task detail.

    LLM_LIVE is only claimed for a task a real model answered (and code accepted); before any
    LLM task runs (the LLM is used in Phase 3 only) the label states the mode found at run start.
    """
    import llm_gateway as g
    st = _load(run_id, "llm", default=None) or {}
    start = st.get("mode_at_start", "unknown")
    if start == g.LLM_DISABLED:
        return f"{g.LLM_DISABLED} (no LLM was called in this run)"
    tasks = [t for t in st.get("tasks", []) if str(t.get("mode", "")).startswith("LLM_")]
    if not tasks:
        where = (f"model {st.get('model')} at {st.get('base_url')}" if start == g.LLM_LIVE
                 else st.get("error") or "no local endpoint")
        return f"{start} at run start ({where}); no LLM task has run yet (LLM tasks run in Phase 3 only)"
    live = [t for t in tasks if t["mode"] == g.LLM_LIVE]
    detail = ", ".join(f"{t['task']}={t['mode']}" for t in tasks)
    if live:
        return f"{g.LLM_LIVE} (model {live[0]['model']}; {detail})"
    return f"{g.LLM_FALLBACK} (deterministic fallback used; {detail})"


def scoring_version(run_id: str) -> str:
    ecfg = _load(run_id, "evidence_config", default=None) or {}
    return ecfg.get("scoring", "v1")


def scoring_label(run_id: str) -> str:
    v = scoring_version(run_id)
    return {"v1": "v1 (relevance: any idea keyword + category vocabulary)",
            "v2": "v2 (relevance: brief-specific user / problem / local terms)"}.get(v, v)


def _with_label(run_id: str, filename: str, content: str) -> str:
    if not filename.endswith((".md", ".txt")) or "LLM mode:" in content[:800]:
        return content
    lines = [] if "Evidence mode" in content[:600] else [f"Evidence mode: {evidence_label(run_id)}"]
    lines.append(f"LLM mode: {llm_label(run_id)}")
    lines.append(f"Scoring version: {scoring_label(run_id)}")
    if filename.endswith(".txt"):
        return "".join(l.replace("Evidence mode:", "evidence mode:") + "\n" for l in lines) + content
    block = "\n".join(f"> {l}" for l in lines)
    first, _, rest = content.partition("\n")
    if first.startswith("# "):
        return f"{first}\n\n{block}\n{rest}"
    return f"{block}\n\n{content}"


def _write(run_id: str, filename: str, content: str) -> pathlib.Path:
    path = out_dir(run_id) / out_name(run_id, filename)
    path.write_text(_with_label(run_id, filename, content), encoding="utf-8")
    return path


def list_outputs(run_id: str) -> list[pathlib.Path]:
    d = out_dir(run_id)
    suffix = DEMO_RUNS.get(run_id)
    files = sorted(p for p in d.iterdir() if p.is_file())
    if suffix is None:
        return files
    stem = lambda p: p.name.rsplit(".", 1)[0]
    if suffix:
        return [p for p in files if stem(p).endswith(suffix)
                and not any(len(s) > len(suffix) and stem(p).endswith(s) for s in DEMO_RUNS.values())]
    return [p for p in files if not any(s and stem(p).endswith(s) for s in DEMO_RUNS.values())]


def _state_path(run_id: str, key: str) -> pathlib.Path:
    d = RUNS / run_id / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def _store(run_id: str, key: str, value) -> None:
    text = value.model_dump_json() if hasattr(value, "model_dump_json") else json.dumps(value)
    _state_path(run_id, key).write_text(text, encoding="utf-8")


def _load(run_id: str, key: str, model=None, default=None):
    p = _state_path(run_id, key)
    if not p.exists():
        return default
    data = json.loads(p.read_text(encoding="utf-8"))
    return model(**data) if model else data


def _counters(run_id: str) -> dict:
    return _load(run_id, "counters", default={"round": 1, "pivots": 0, "build_attempt": 1, "history": []})


def _spawn(fn, *args):
    if getattr(_mode, "sync", False):
        fn(*args)
    else:
        threading.Thread(target=fn, args=args, daemon=True).start()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_run(brief_text: str, run_id: str | None = None, auto_approve: bool = False,
              evidence_cfg: dict | None = None) -> str:
    """evidence_cfg: {"mode": "live"|"replay", "snapshot": path, "capture": bool} (default: live)."""
    db.init_db()
    run_id = run_id or secrets.token_hex(8)
    db.create_run(run_id, secrets.token_hex(16), json.dumps({"raw": brief_text}),
                  datetime.now(timezone.utc).isoformat(), auto_approve=auto_approve)
    import evidence as _ev
    cfg = dict(evidence_cfg or {"mode": "live", "capture": False})
    import os as _os
    live_default = _os.environ.get("HATCHAI_SCORING") or _ev.DEFAULT_LIVE_SCORING   # new live runs: v2
    cfg.setdefault("scoring", live_default if cfg.get("mode") != "replay" else "v1")
    if cfg["scoring"] not in _ev.SCORING_VERSIONS:
        raise ValueError(f"unknown scoring version {cfg['scoring']!r}")
    db.set_run_scoring(run_id, cfg["scoring"])
    _store(run_id, "evidence_config", cfg)
    _record_llm_mode(run_id)
    db.update_run_status(run_id, "phase_1_running", phase=1)
    _spawn(_run_phase_1, run_id)
    return run_id


def advance_after_gate(run_id: str, gate_id: int, decision: str) -> None:
    c = _counters(run_id)
    if decision == "stop":
        db.update_run_status(run_id, "stopped", error=f"Founder stopped the run at gate {gate_id}")
        callbacks.log(run_id, "orchestrator", "run_stopped", phase=gate_id, outcome="stop")
        return
    if decision in ("approve", "override_stop"):
        nxt = NEXT_PHASE.get(gate_id)
        if nxt:
            _spawn(PHASES[nxt], run_id)
        return
    if decision == "repeat":
        if gate_id in (1, 2):
            c["round"] += 1
            _store(run_id, "counters", c)
            _spawn(_run_phase_1, run_id)
        elif gate_id == 3:
            c["build_attempt"] += 1
            _store(run_id, "counters", c)
            _spawn(_run_phase_3, run_id)
        return
    if decision == "pivot":
        gate = db.get_gate_result(run_id, gate_id)
        c["pivots"] += 1
        c["round"] = 1
        c["pivot_idea"] = gate.get("pivot_to") or ""
        _store(run_id, "counters", c)
        _state_path(run_id, "findings").unlink(missing_ok=True)
        callbacks.log(run_id, "orchestrator", "pivot", phase=gate_id, outcome=c["pivot_idea"][:120])
        _spawn(_run_phase_1, run_id)


def _advise(run_id: str, gate_id: int, gate: GateResult, step: int, features=None) -> dict | None:
    """Write the Advisor memo for this gate. Advisory: a failure here is logged, never fatal."""
    try:
        from agents.advisor import run as advisor_run
        c = _counters(run_id)
        res = advisor_run(run_id, gate_id, gate, _load(run_id, "brief", FounderBrief),
                          _load(run_id, "findings", ResearchFindings),
                          critique=_load(run_id, "critique", Critique),
                          features=features, demand_test=_load(run_id, "demand_test", DemandTest),
                          round_no=c["round"], pivots=c["pivots"])
        _write(run_id, f"phase{gate_id}_step{step}_advisor-memo.md", res["memo"])
        return res
    except Exception as exc:   # advisory layer must never block the pipeline
        log.warning("advisor memo failed for %s gate %s: %s", run_id, gate_id, exc)
        callbacks.log(run_id, "advisor", f"advisor_memo_gate_{gate_id}_failed", phase=gate_id,
                      outcome=f"{type(exc).__name__}: {exc}"[:300])
        return None


def _gate(run_id: str, gate: GateResult, phase: int, extra: str = "") -> None:
    c = _counters(run_id)
    c["history"].append({"gate": gate.gate_id, "outcome": gate.outcome.value, "round": c["round"],
                         "E": gate.evidence_score, "V": gate.viability_score})
    _store(run_id, "counters", c)
    db.save_gate_result(run_id, gate.gate_id, gate.outcome.value, gate.evidence_score,
                        gate.viability_score, gate.reason, gate.checks, gate.pivot_to)
    callbacks.log(run_id, "gate", f"gate_{gate.gate_id}_evaluation", phase=phase, outcome=gate.outcome.value)
    _write(run_id, f"phase{phase}_gate_decision.md", _format_gate(gate, c["history"]) + extra)
    db.update_run_status(run_id, f"gate_{gate.gate_id}_pending", phase=phase)
    run = db.get_run(run_id)
    if run and run.get("auto_approve"):
        _auto_decide(run_id, gate)


def _auto_decide(run_id: str, gate: GateResult) -> None:
    """Demo/--yes mode: the founder pre-consented to follow each gate's recommendation."""
    decision = {"go": "approve", "repeat": "repeat", "pivot": "pivot", "stop": "stop"}[gate.outcome.value]
    token = db.get_run(run_id)["founder_token"]
    ok, err = approval.record_decision(run_id, gate.gate_id, decision, token,
                                       via="auto: CLI --yes follows gate recommendation")
    if ok:
        advance_after_gate(run_id, gate.gate_id, decision)
    else:
        log.error("auto decision failed: %s", err)


def _fail(run_id: str, phase: int, exc: Exception) -> None:
    log.exception("Phase %s failed for run %s", phase, run_id)
    db.update_run_status(run_id, "failed", error=f"Phase {phase}: {exc}")


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------

def _run_phase_1(run_id: str):
    try:
        db.update_run_status(run_id, "phase_1_running", phase=1)
        run = db.get_run(run_id)
        brief_text = json.loads(run["brief_json"])["raw"]
        c = _counters(run_id)
        pivot_idea = c.get("pivot_idea", "")

        blocked, reason = gates.guardrail_0(f"{brief_text}\n{pivot_idea}")
        if blocked:
            callbacks.log(run_id, "gate", "guardrail_0_block", phase=1, outcome="stop")
            _write(run_id, "phase1_gate_decision.md",
                   f"# Gate 1 — BLOCKED by Guardrail 0\n\n**Reason:** {reason}\n\n"
                   "This run cannot proceed. Guardrail 0 blocks have no override.\n")
            db.update_run_status(run_id, "stopped", error="Guardrail 0: " + reason)
            return

        import evidence as evidence_mod
        from agents.intake import run as intake_run
        from agents.researcher import run as research_run

        brief = _load(run_id, "brief", FounderBrief)
        if brief is None:
            brief = intake_run(run_id, brief_text)
            _store(run_id, "brief", brief)
        if pivot_idea and brief.idea != pivot_idea:
            brief.assumptions.append(f"PIVOT from original idea: {brief.idea}")
            brief.idea = pivot_idea
            _store(run_id, "brief", brief)

        previous = _load(run_id, "findings", ResearchFindings) if c["round"] > 1 else None
        ecfg = _load(run_id, "evidence_config", default={"mode": "live"}) or {"mode": "live"}
        snapshot = load_snapshot(ecfg["snapshot"]) if ecfg.get("mode") == "replay" else None
        captured = _load(run_id, "capture_rounds", default=[]) if ecfg.get("capture") else None
        try:
            findings = research_run(run_id, brief, round_no=c["round"], previous=previous,
                                    replay=snapshot, capture=captured, scoring=ecfg.get("scoring", "v1"))
        except evidence_mod.ReplayMissError as exc:
            if snapshot is not None and ecfg.get("scoring", "v1") != snapshot.get("scoring_version", "v1"):
                # The newer scoring asked for research the snapshot never captured: end honestly.
                msg = (f"replay under scoring {ecfg['scoring']} needs evidence the snapshot does not contain "
                       f"(captured under {snapshot.get('scoring_version', 'v1')}): {exc}")
                callbacks.log(run_id, "orchestrator", "replay_round_not_captured", phase=1, outcome=msg[:300])
                db.update_run_status(run_id, "stopped", error=msg)
                return
            raise
        gate = gates.evaluate_gate_1(findings, brief, round_no=c["round"], pivots_used=c["pivots"])
        _store(run_id, "findings", findings)
        if captured is not None:
            captured[-1]["evidence_score_at_capture"] = gate.evidence_score
            _store(run_id, "capture_rounds", captured)

        _write(run_id, "phase1_step1_intake.md", _format_brief(brief))
        _write(run_id, "phase1_step2_research-findings.md", _format_findings(findings))
        _write(run_id, "phase1_step3_sources.json", json.dumps(
            [s.model_dump() for s in findings.sources], indent=2, ensure_ascii=False))
        _advise(run_id, 1, gate, 5)
        replay_note = ""
        if findings.evidence_mode == "replay":
            replay_note = (f"\n> **Evidence mode: REPLAY** of snapshot {findings.snapshot}. No new evidence was "
                           "collected in this run; the gate re-scored the captured sources with the current code.\n")
        _gate(run_id, gate, 1, replay_note)
    except Exception as exc:
        _fail(run_id, 1, exc)


def _run_phase_2(run_id: str):
    try:
        db.update_run_status(run_id, "phase_2_running", phase=2)
        from agents.validator import run_canvas, run_critique, run_demand_test

        brief = _load(run_id, "brief", FounderBrief)
        findings = _load(run_id, "findings", ResearchFindings)
        findings.evidence_score = gates.compute_evidence_score(findings)
        c = _counters(run_id)

        critique = run_critique(run_id, brief, findings)
        canvas = run_canvas(run_id, brief, findings, critique)
        demand_test = run_demand_test(run_id, brief, canvas)
        gate = gates.evaluate_gate_2(findings, critique, round_no=c["round"], pivots_used=c["pivots"])
        critique.recommendation = gate.outcome

        _store(run_id, "critique", critique)
        _store(run_id, "canvas", canvas)
        _store(run_id, "demand_test", demand_test)
        _write(run_id, "phase2_step1_critique.md", _format_critique(critique))
        _write(run_id, "phase2_step2_lean-canvas.md", _format_canvas(canvas, findings))
        _write(run_id, "phase2_step3_demand-test-plan.md", _format_demand_test(demand_test))
        _advise(run_id, 2, gate, 4)
        _gate(run_id, gate, 2)
    except Exception as exc:
        _fail(run_id, 2, exc)


def _run_phase_3(run_id: str):
    try:
        db.update_run_status(run_id, "phase_3_running", phase=3)
        from agents.builder import run as build_run

        brief = _load(run_id, "brief", FounderBrief)
        canvas = _load(run_id, "canvas", LeanCanvas)
        critique = _load(run_id, "critique", Critique)
        c = _counters(run_id)

        report = build_run(run_id, brief, canvas, critique, attempt=c["build_attempt"],
                           ref_date=_reference_date(run_id))
        llm_state = _load(run_id, "llm", default={}) or {}
        llm_state["tasks"] = llm_state.get("tasks", []) + report.get("llm_tasks", [])
        _store(run_id, "llm", llm_state)
        gate = gates.evaluate_gate_3(report, attempt=c["build_attempt"])
        if not report.get("supported", True):
            # No template fits: write a spec-only document; never claim an MVP exists.
            _store(run_id, "app", {"supported": False, "reason": report["unsupported_reason"]})
            _write(run_id, "phase3_step1_mvp-spec.md", _format_unsupported_spec(report, brief, canvas, critique))
            _advise(run_id, 3, gate, 4)
            _gate(run_id, gate, 3)
            return
        _store(run_id, "app", {"product_name": report["spec"].product_name, "app_dir": str(report["app_dir"]),
                               "archetype": report["spec"].archetype, "supported": True})

        _write(run_id, "phase3_step1_mvp-spec.md", _format_mvp_spec(report, canvas))
        _write(run_id, "phase3_step2_mvp-source.md", _format_mvp_source(report))
        _write(run_id, "phase3_step3_mvp-test-report.txt", _format_test_report(report))
        adv = _advise(run_id, 3, gate, 4, features=report["spec"].features)
        cov = (adv or {}).get("coverage")
        extra = ("" if not cov else
                 f"\n> **Advisory, not part of the gate:** the MVP covers **{cov['covered']} of {cov['total']}** "
                 "verified pains in the demand evidence. See `phase3_step4_advisor-memo.md`.\n")
        if adv and not cov:
            extra = ("\n> **Advisory, not part of the gate:** no verified pain was found in the demand evidence, "
                     "so feature fit is untested. See `phase3_step4_advisor-memo.md`.\n")
        _gate(run_id, gate, 3, extra)
    except Exception as exc:
        _fail(run_id, 3, exc)


def _run_phase_4(run_id: str):
    try:
        db.update_run_status(run_id, "phase_4_running", phase=4)
        from agents.commercial import run as commercial_run

        brief = _load(run_id, "brief", FounderBrief)
        canvas = _load(run_id, "canvas", LeanCanvas)
        findings = _load(run_id, "findings", ResearchFindings)
        app = _load(run_id, "app", default={})
        result = commercial_run(run_id, brief, canvas, findings, app.get("product_name", ""))
        _store(run_id, "pricing", result["pricing_data"])
        gate = gates.evaluate_gate_4(result["pricing"], result["policies"])
        _write(run_id, "phase4_step1_pricing.md", result["pricing"])
        _write(run_id, "phase4_step2_policies.md", result["policies"])
        _gate(run_id, gate, 4)
    except Exception as exc:
        _fail(run_id, 4, exc)


def _run_phase_5(run_id: str):
    try:
        db.update_run_status(run_id, "phase_5_running", phase=5)
        from payments import checkout, init_payments, process_checkout
        from reconcile import format_payment_log, run_reconciliation
        from refunds import process_refund

        init_payments()
        brief = _load(run_id, "brief", FounderBrief)
        app = _load(run_id, "app", default={})
        pricing = _load(run_id, "pricing", default={"plus": 4.0})

        drafts = _draft_launch_copy(brief, app.get("product_name", brief.idea[:40]), pricing)
        callbacks.log(run_id, "launch", "draft_launch_copy", phase=5, outcome="pending_founder_approval")
        _write(run_id, "phase5_step1_launch-drafts.md", drafts)

        amount = int(round(pricing.get("plus", 4.0) * 100))  # minor units (cents)
        co = checkout(run_id, amount_minor=amount)
        paid = process_checkout(co["payload"], co["signature"])
        replay = process_checkout(co["payload"], co["signature"])
        refund = process_refund(co["order_id"])
        recon = run_reconciliation(run_id)
        plog = format_payment_log(run_id, paid, refund, replay, recon)
        callbacks.log(run_id, "payments", "sale_to_cash_simulation_mocked", phase=5)
        _write(run_id, "payment_test_log.md", plog)
        _store(run_id, "payment", {"orders": recon.get("orders_checked", 0),
                                   "refunds": sum(1 for r in recon.get("results", []) if r["status"] == "REFUNDED")})
        _gate(run_id, gates.evaluate_gate_5(plog, drafts), 5)
    except Exception as exc:
        _fail(run_id, 5, exc)


def _run_phase_6(run_id: str):
    try:
        db.update_run_status(run_id, "phase_6_running", phase=6)
        from agents.operate import run as operate_run

        _write_operate_memo(run_id, operate_run)
        db.update_run_status(run_id, "completed", phase=6)
        callbacks.log(run_id, "orchestrator", "run_completed", phase=6, outcome="completed")
    except Exception as exc:
        _fail(run_id, 6, exc)


def _write_operate_memo(run_id: str, operate_run) -> str:
    brief = _load(run_id, "brief", FounderBrief)
    dt = _load(run_id, "demand_test", DemandTest)
    app = _load(run_id, "app", default={}) or {}
    memo = operate_run(run_id, brief, dt, pathlib.Path(app["app_dir"]) if app.get("app_dir") else None,
                       _load(run_id, "payment", default={}))
    return _write(run_id, "phase6_step1_operate-memo.md", memo).read_text(encoding="utf-8")


def measure(run_id: str) -> str:
    """Re-run Phase 6 on a completed run: read the MVP's stored counts again."""
    run = db.get_run(run_id)
    if not run or run["status"] != "completed":
        raise ValueError(f"run {run_id} must be completed before re-measuring (status: {run and run['status']})")
    from agents.operate import run as operate_run
    callbacks.log(run_id, "orchestrator", "remeasure_phase_6", phase=6)
    return _write_operate_memo(run_id, operate_run)


PHASES = {1: _run_phase_1, 2: _run_phase_2, 3: _run_phase_3, 4: _run_phase_4, 5: _run_phase_5, 6: _run_phase_6}


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_brief(brief: FounderBrief) -> str:
    rows = "\n".join(f"| {k.replace('_', ' ').title()} | {getattr(brief, k)} |" for k in
                     ("idea", "target_user", "geography", "language", "skills", "budget_usd", "hours_per_week",
                      "values"))
    return f"""# Phase 1 — Intake

| Field | Value |
|---|---|
{rows}

**Fields the founder did not state (marked UNKNOWN / ASSUMPTION by code):** {', '.join(brief.unknown_fields) or 'none'}

## Assumptions

{chr(10).join(f"- {a}" for a in brief.assumptions) or "- none"}
"""


def _format_findings(f: ResearchFindings) -> str:
    import evidence as _ev
    by_key = {s.key: s for s in f.sources}
    lines = []
    for c in f.claims:
        cites = ", ".join(f"[{k}]({by_key[k].url})" for k in c.source_keys if k in by_key)
        tag = f"VERIFIED — {cites}" if c.verified else "**ASSUMPTION**"
        lines.append(f"- **{c.category}** — {c.text} ({tag})")
    breakdown = gates.evidence_breakdown(f)
    evidence_line = (f"> **Evidence mode: REPLAY** — sources loaded from snapshot {f.snapshot}. Nothing was collected "
                     "in this run; fetch times and hashes below are the ORIGINAL capture values.\n"
                     if f.evidence_mode == "replay" else
                     "> Evidence mode: **live** — sources collected during this run.\n")
    return f"""# Phase 1 — Research findings (round {f.research_round})

{evidence_line}> Synthesis mode: **{f.mode}** ({'open-weight LLM, quotes re-verified by code' if f.mode == 'llm' else 'no LLM: claims are verbatim passages from fetched sources'}).
> Every claim cites a fetched source whose text contains the quoted passage, or is labelled ASSUMPTION.

## Claims

{chr(10).join(lines)}

## Opportunity angles

{chr(10).join(f"- {a}" for a in f.opportunity_angles)}

## Evidence score: {gates.compute_evidence_score(f)} / 100

| Component | Points |
|---|---|
{chr(10).join(f"| {k.replace('_', ' ')} | {v} |" for k, v in breakdown.items())}

{_format_quality(f)}

## Source ledger ({len(f.sources)} sources, {len({s.domain for s in f.sources})} domains)

{chr(10).join(f"- `{s.key}` [{s.title}]({s.url}) — {s.collector}, {s.category}, {_ev.credibility(s)}, published {_ev.source_date(s)[0] or 'undated'}, fetched {s.fetch_time}, sha256:{s.text_hash}" for s in f.sources) or "- none fetched"}
"""


def _format_quality(f: ResearchFindings) -> str:
    """Freshness / credibility / passage-origin audit of the verified claims (advisory, not scored)."""
    import evidence as _ev
    q = _ev.quality_report(f.sources, f.claims)
    sm = q["summary"]
    rows = "\n".join(
        f"| {r['category']} | {r['key']} | {r['domain']} | {r['credibility']} | {r['published'] or 'undated'}"
        f"{' (' + r['date_from'] + ')' if r['date_from'] else ''} | {r['freshness']}"
        f"{'' if r['age_days'] is None else ' (' + str(r['age_days']) + ' d)'} | {r['origin']} |"
        for r in q["rows"]) or "| – | – | – | – | – | – | – |"
    warn = "\n".join(f"- ⚠ {w}" for w in q["warnings"]) or "- none"
    return f"""## Evidence quality audit (advisory: shown to the founder, not part of the E score)

A quote that matches its source proves **where** a sentence came from, not that it is **true**. This audit
shows who is speaking, how old the source is, and whether the quote came from the fetched page or only from
the search engine's snippet. Freshness: fresh ≤ 18 months, aging ≤ 36 months, stale > 36 months (age measured
at fetch time).

| Metric | Value |
|---|---|
| Cited sources | {sm['cited_sources']} |
| Dated (publication date found) | {int(sm['dated_share'] * 100)}% |
| Fresh (≤ 18 months) | {int(sm['fresh_share'] * 100)}% |
| Independent (not a vendor writing about its own market) | {int(sm['independent_share'] * 100)}% |
| Quotes taken from a search snippet rather than the page | {int(sm['snippet_quote_share'] * 100)}% |
| Categories backed by independent, non-stale evidence | {', '.join(sm['categories_with_independent_non_stale_evidence']) or 'none'} |
| Categories backed only by vendor or stale evidence | {', '.join(sm['categories_only_vendor_or_stale']) or 'none'} |

| Category | Source | Domain | Who is speaking | Published | Freshness | Quote origin |
|---|---|---|---|---|---|---|
{rows}

**Warnings**

{warn}"""


def _format_gate(g: GateResult, history: list) -> str:
    checks = "\n".join(f"- {'✓' if v else '✗'} {k.replace('_', ' ')}" for k, v in g.checks.items())
    hist = "\n".join(f"| {h['gate']} | {h['round']} | {h['outcome'].upper()} | {h['E']} | {h['V']} |" for h in history)
    pivot = f"\n**Suggested pivot:** {g.pivot_to}\n" if g.pivot_to else ""
    return f"""# Gate {g.gate_id} decision

**Recommendation (computed by code): {g.outcome.value.upper()}**

{g.reason}
{pivot}
## Checks

{checks}

## Founder decision

Required before anything proceeds — see `decision_log.json` (`gate_{g.gate_id}_decision`, `approved_by: founder`).

## Gate history for this run

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
{hist}
"""


def _format_critique(c: Critique) -> str:
    risks = "\n".join(f"| {a.assumption} | {a.risk} | {a.kill_criterion} | {'; '.join(a.evidence_gaps) or '—'} |"
                      for a in c.riskiest_assumptions)
    vb = "\n".join(f"| {k.replace('_', ' ')} | {v} |" for k, v in c.viability_breakdown.items())
    return f"""# Phase 2 — Red-team critique

## Summary

{c.summary}

## Viability score (computed by code): {c.viability_score} / 5

| Component | Points |
|---|---|
{vb}

## Demand signal

{c.demand_signal}

## Founder fit

{c.founder_fit}

## Riskiest assumptions and kill criteria

| Assumption | Risk | Kill criterion | Evidence gaps |
|---|---|---|---|
{risks}

**Gate 2 recommendation:** {c.recommendation.value.upper()}
"""


def _format_canvas(canvas: LeanCanvas, f: ResearchFindings) -> str:
    by_key = {s.key: s.url for s in f.sources}
    rows = []
    for b in (canvas.problem, canvas.customer_segments, canvas.unique_value_proposition, canvas.solution,
              canvas.channels, canvas.revenue_streams, canvas.cost_structure, canvas.key_metrics,
              canvas.unfair_advantage):
        cite = ", ".join(f"[{k}]({by_key.get(k, '#')})" for k in b.source_keys)
        rows.append(f"| **{b.block}** | {b.content.replace('|', '/')[:300]} | {cite or 'ASSUMPTION'} |")
    return "# Phase 2 — Lean Canvas\n\n| Block | Content | Evidence |\n|---|---|---|\n" + "\n".join(rows) + "\n"


def _format_demand_test(dt: DemandTest) -> str:
    return f"""# Phase 2 — Pre-registered demand test

> Status: **{dt.status}**. Thresholds are fixed before any data exists. Simulated results are never used as evidence.

| Field | Value |
|---|---|
| Channel | {dt.channel} |
| Metric | {dt.metric} |
| Decision rule | {dt.threshold} |
| Duration | {dt.duration_days} days |
| Cost (USD) | {dt.cost_usd} |

The waitlist form is part of the Phase 3 MVP (consent required); Phase 6 reads the real sign-up count.
"""


def _format_mvp_spec(r: dict, canvas: LeanCanvas) -> str:
    s = r["spec"]
    feats = "\n".join(f"| {f.name} | {f.description} | `{f.action}` | {f.traces_to[:120]} |" for f in s.features)
    fields = ", ".join(f"`{f.name}` ({f.type})" for f in s.fields)
    t = r["tests"]
    return f"""# Phase 3 — MVP spec and build: {s.product_name}

> {s.tagline}

**Status:** generated, tested and booted by the pipeline — {t['ran']} tests, {t['failed']} failures,
{t['errors']} errors; smoke test {'passed' if r['smoke_ok'] else 'FAILED'}. Build attempt {r['attempt']}.

## Archetype

`{s.archetype}` — {r.get('template_reason', '')} All scores: {r['archetype_scores']}.

## Features (each traced to a problem or risk, each verified by a generated test)

| Feature | What it does | API action | Traces to |
|---|---|---|---|
{feats}

## LLM use (bounded; never code, scores or gate decisions)

{_format_llm_tasks(r.get("llm_tasks", []))}

## Data model

{s.item_label} fields: {fields}. Seed content: {len(s.seed_items)} items, **SAMPLE DATA**
({'written by ' + r['model'] if r['model'] else 'deterministic, derived from the brief'}).

## Scope

- In: the features above, JSON API, web UI ({', '.join(s.languages)}{', RTL toggle' if 'ar' in s.languages else ''}), consented waitlist, free-tier item limit ({s.free_tier_limit}).
- Out: accounts/auth, real payments (MOCKED), analytics (STUBBED), hosting/deployment (founder decision).

## Run it

```bash
cd {r['app_dir'].relative_to(r['app_dir'].parent.parent).as_posix()}
python server.py --port 8080          # http://localhost:8080
python -m unittest discover -s tests -v
```

Files: {', '.join(r['file_list'])}
"""


def _format_llm_tasks(tasks: list) -> str:
    if not tasks:
        return "- No LLM task ran in this build."
    out = []
    for t in tasks:
        extra = t.get("error") or ""
        if t["task"] == "template_suggestion" and t.get("accepted"):
            extra = f"accepted synonyms {t['accepted']}; selection changed: {t['changed_selection']}"
        if t["task"] == "spec_text" and t.get("applied"):
            extra = "product name and tagline written by the model and accepted by code"
        model = f", model {t['model']}" if t.get("model") else ""
        out.append(f"- `{t['task']}`: **{t['mode']}**{model}" + (f" — {extra}" if extra else ""))
    return "\n".join(out)


def _format_unsupported_spec(r: dict, brief: FounderBrief, canvas: LeanCanvas, critique: Critique) -> str:
    rows = "\n".join(f"| `{a}` | {s} | {', '.join(r['template_matches'][a]) or '—'} |"
                     for a, s in sorted(r["archetype_scores"].items(), key=lambda x: -x[1]))
    risk = critique.riskiest_assumptions[0].assumption if critique.riskiest_assumptions else "—"
    return f"""# Phase 3 — UNSUPPORTED: no MVP was built (spec only, STUBBED)

> **No code was generated, no tests were run, and no server was started.**
> HatchAI only builds MVPs from templates whose domain logic is tested. None fits this idea,
> so the system says so instead of forcing it into the closest template.

## Why

{r['unsupported_reason']}

| Template | Compatibility score | Matched keywords |
|---|---|---|
{rows}

## What a builder would need to make (spec only)

- **Idea:** {brief.idea}
- **Target user:** {brief.target_user}
- **Problem (Lean Canvas):** {canvas.problem.content.split(' Evidence:')[0]}
- **Riskiest assumption to test first:** {risk}
- **Smallest test of demand:** a landing page with a consented waitlist (see the Phase 2 demand-test plan).

## LLM use

{_format_llm_tasks(r.get("llm_tasks", []))}

## Founder options at Gate 3

- **Stop** (recommended by the gate), or
- **Override with a written reason** to continue to pricing and launch planning *without* an MVP
  (the founder builds it manually or with another tool).
"""


def _format_mvp_source(r: dict) -> str:
    d = r["app_dir"]
    parts = [f"# Phase 3 — Generated MVP source: {r['spec'].product_name}\n",
             "Idea-specific files are shown in full. Shared runtime files (server.py, store.py, index.html, "
             "tests/test_server.py) are copied from `mvp_templates/_shared/`.\n"]
    for name, lang in (("config.json", "json"), ("tests/test_spec.py", "python"), ("core.py", "python")):
        parts.append(f"## `{name}`\n\n```{lang}\n{(d / name).read_text(encoding='utf-8')}\n```\n")
    return "\n".join(parts)


def _format_test_report(r: dict) -> str:
    t = r["tests"]
    return (f"HatchAI Phase 3 — generated MVP verification\nproduct: {r['spec'].product_name}\n"
            f"archetype: {r['spec'].archetype}\nattempt: {r['attempt']}\n"
            f"command: python -m unittest discover -s tests -v  (cwd={r['app_dir'].name})\n"
            f"result: ran={t['ran']} failures={t['failed']} errors={t['errors']} ok={t['ok']} ({t['seconds']} s)\n"
            f"smoke: {'PASS' if r['smoke_ok'] else 'FAIL'} — {r['smoke_msg']}\n\n--- raw output ---\n{t['output']}")


def _draft_launch_copy(brief: FounderBrief, product: str, pricing: dict) -> str:
    return f"""# Phase 5 — Launch drafts

> **PENDING_FOUNDER_APPROVAL** — nothing here has been posted, sent or published.
> Drafts are written in the founder's own voice and must be posted by the founder personally.
> No testimonials, user counts, countdowns or outcome promises are included.

## Community post draft

I'm building **{product}** for {brief.target_user} in {brief.geography}. It's an early, free MVP.
I'd value honest feedback — what would make it worth using every week? There is a waitlist on the page
if you want to hear when it improves. (Paid plan, if any, would be about USD {pricing.get('plus', 0):.2f}/month; the core stays free.)

## Store / landing listing draft

**{product}** — a focused tool for {brief.target_user}. Free core features. Early version: expect rough edges.

## Approval checklist (founder)

- [ ] Facts in the copy are true today
- [ ] Posted from my own account, in communities whose rules allow it
- [ ] Waitlist consent text reviewed
"""


# ---------------------------------------------------------------------------
# CLI
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


def _reference_date(run_id: str):
    """'Today' for date-dependent sample content: live -> None (real clock); replay -> capture date."""
    from datetime import date
    ecfg = _load(run_id, "evidence_config", default={}) or {}
    if ecfg.get("mode") != "replay":
        return None
    return date.fromisoformat(load_snapshot(ecfg["snapshot"])["captured_at"][:10])


def _reset_run(run_id: str):
    import shutil
    from payments import init_payments
    shutil.rmtree(RUNS / run_id, ignore_errors=True)
    db.init_db()      # a fresh database (first command, or an isolated test) has no tables yet
    init_payments()   # make sure the simulation tables exist before clearing them
    with db.get_conn() as conn:
        for t in ("gate_results", "decision_log", "runs"):
            conn.execute(f"DELETE FROM {t} WHERE run_id=?", (run_id,))
        # Simulated sale-to-cash rows of this run (entitlements and events are keyed by order id)
        orders = "SELECT order_id FROM orders WHERE run_id=?"
        conn.execute(f"DELETE FROM entitlements WHERE order_id IN ({orders})", (run_id,))
        conn.execute(f"DELETE FROM payment_events WHERE order_id IN ({orders})", (run_id,))
        conn.execute("DELETE FROM orders WHERE run_id=?", (run_id,))
    for p in OUTPUTS.glob("*"):
        if run_id in DEMO_RUNS and p.is_file() and p in list_outputs(run_id):
            p.unlink()


def run_sync(brief_text: str, run_id: str, auto: bool = True, interactive: bool = True,
             evidence_cfg: dict | None = None) -> dict:
    """Run a full pipeline in this thread (CLI/demo). Returns the final run row."""
    db.init_db()
    _mode.sync = True
    try:
        start_run(brief_text, run_id=run_id, auto_approve=auto, evidence_cfg=evidence_cfg)
        if not auto and interactive:
            _interactive(run_id)
    finally:
        _mode.sync = False
    return db.get_run(run_id)


def _interactive(run_id: str):
    while True:
        run = db.get_run(run_id)
        st = run["status"]
        if not (st.startswith("gate_") and st.endswith("_pending")):
            return
        gid = int(st.split("_")[1])
        g = db.get_gate_result(run_id, gid)
        print(f"\nGate {gid}: {g['outcome'].upper()} — {g['reason']}")
        allowed = sorted(approval.ALLOWED[g["outcome"]])
        choice = input(f"Founder decision {allowed}: ").strip()
        reason = input("Written reason: ").strip() if choice == "override_stop" else ""
        ok, err = approval.record_decision(run_id, gid, choice, run["founder_token"], reason)
        if not ok:
            print("Rejected:", err)
            continue
        advance_after_gate(run_id, gid, choice)


def _demo_test_traffic(run_id: str, visitors: int = 300, signups: int = 20) -> None:
    """Demo only: verify the Phase 6 measurement path with clearly labelled TEST traffic."""
    app = _load(run_id, "app", default={}) or {}
    if db.get_run(run_id)["status"] != "completed" or not app.get("app_dir"):
        return
    from demand_test_traffic import send_test_traffic
    res = send_test_traffic(app["app_dir"], visitors=visitors, signups=signups)
    callbacks.log(run_id, "demo_script", "send_labelled_test_traffic", phase=6,
                  outcome=f"TEST only: {visitors} visitors, {signups} sign-ups (X-HatchAI-Traffic: TEST, @example.com)")
    measure(run_id)
    t, r = res["metrics"]["test"], res["metrics"]["real"]
    print(f"[{run_id}] TEST traffic sent and re-measured: TEST {t['unique_visitors']} visitors / {t['signups']} "
          f"sign-ups; REAL {r['unique_visitors']} visitors / {r['signups']} sign-ups")


# ---------------------------------------------------------------------------
# Evidence snapshots: capture a live run, replay it reproducibly
# ---------------------------------------------------------------------------

def load_snapshot(path) -> dict:
    snap = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if snap.get("snapshot_version") != 1:
        raise ValueError(f"unsupported snapshot version in {path}")
    p = pathlib.Path(path).resolve()
    snap["_file"] = p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.name
    return snap


def _git_state() -> dict:
    import subprocess
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return {"commit": head, "uncommitted_changes": bool(dirty) if head else None}
    except Exception:
        return {"commit": None, "uncommitted_changes": None}


def _capture_metadata(rounds: list) -> dict:
    import evidence
    import llm_gateway
    collectors = sorted({s["collector"] for r in rounds for s in r["sources"]})
    return {
        "capture_date": datetime.now(timezone.utc).date().isoformat(),
        "search_method": {
            "collectors_used": collectors,
            "web_search": f"ddgs metasearch, backends tried in order: {', '.join(evidence._WEB_BACKENDS)}",
            "other_sources": "Hacker News Algolia API, Wikipedia MediaWiki API, World Bank Indicators API",
            "page_fetch": "httpx GET of each web result; up to 3 keyword-ranked sentences kept per page",
            "query_planner": "evidence.plan_queries (round 1: category queries; round 2: broadened)",
            "synthesis_model": llm_gateway.active_model_label(),
            "text_hash": "first 16 hex chars of SHA-256 over ' '.join(passages) as stored",
        },
        "code_state": _git_state(),
    }


def write_snapshot(run_id: str, path, label: str = "") -> dict:
    """Save the evidence a live (capture-enabled) run actually collected, plus its gate outcomes."""
    rounds = _load(run_id, "capture_rounds", default=None)
    if not rounds:
        raise ValueError(f"run {run_id} has no captured evidence (start it with capture enabled)")
    run = db.get_run(run_id)
    snap = {
        "snapshot_version": 1,
        "label": label or run_id,
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "captured_from_run": run_id,
        "brief": json.loads(run["brief_json"])["raw"],
        "note": ("Evidence captured from a live HatchAI run (real web/HN/Wikipedia/World Bank fetches). "
                 "Replaying it re-runs verification, scoring and gates without any network access."),
        "capture_metadata": _capture_metadata(rounds),
        "scoring_version": scoring_version(run_id),
        "rounds": rounds,
        "gate_outcomes_at_capture": _counters(run_id)["history"],
        "final_status_at_capture": run["status"],
    }
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
    return snap


def capture(brief_text: str, path, run_id: str | None = None, label: str = "") -> dict:
    """Live run with capture enabled (gate recommendations followed), saved as a snapshot."""
    run_id = run_id or "capture-" + secrets.token_hex(4)
    _reset_run(run_id)
    run_sync(brief_text, run_id, auto=True, evidence_cfg={"mode": "live", "capture": True})
    return write_snapshot(run_id, path, label)


def _gate_signature(history: list) -> list:
    return [(h["gate"], h["outcome"], h["round"], h["E"], h["V"]) for h in history]


def replay(path, run_id: str = "demo-replay", scoring: str | None = None) -> dict:
    """Re-run a captured scenario from its snapshot: no network, no LLM, deterministic.

    scoring: relevance rule to apply (default: the version the snapshot was captured under, so the
    captured outcomes are reproduced). A different version may legitimately give different outcomes;
    that is reported as a labelled scoring-version difference, not as a mismatch."""
    import os
    snap = load_snapshot(path)
    captured_v = snap.get("scoring_version", "v1")
    scoring = scoring or captured_v
    saved = {k: os.environ.get(k) for k in ("HATCHAI_OFFLINE", "HATCHAI_NO_LLM")}
    os.environ.update(HATCHAI_OFFLINE="1", HATCHAI_NO_LLM="1")
    try:
        _reset_run(run_id)
        run = run_sync(snap["brief"], run_id, auto=True,
                       evidence_cfg={"mode": "replay", "snapshot": str(path), "capture": False,
                                     "scoring": scoring})
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    replayed = _counters(run_id)["history"]
    same = _gate_signature(replayed) == _gate_signature(snap["gate_outcomes_at_capture"])
    version_diff = scoring != captured_v
    match = same and not version_diff
    verdict = ("MATCH" if match else
               f"SCORING-VERSION DIFFERENCE (captured under {captured_v}, replayed under {scoring})"
               if version_diff else "DIFFER FROM")
    callbacks.log(run_id, "orchestrator", "replay_check", phase=1,
                  outcome=f"gate outcomes {verdict} capture of {snap['captured_at']}")
    _write(run_id, "phase1_step4_evidence-replay-check.md",
           _format_replay_check(snap, replayed, run, match, scoring, captured_v))
    return {"run": run, "match": match, "replayed": replayed, "captured": snap["gate_outcomes_at_capture"],
            "scoring": scoring, "captured_scoring": captured_v, "scoring_difference": version_diff,
            "same_outcomes": same}


def _outcome_line(h: list) -> str:
    return " → ".join(f"G{x['gate']}:{x['outcome'].upper()}(E={x['E']},V={x['V']})" for x in h) or "none"


def _format_replay_check(snap: dict, replayed: list, run: dict, match: bool, scoring: str = "v1",
                         captured_v: str = "v1") -> str:
    def rows(h):
        return "\n".join(f"| G{x['gate']} | {x['round']} | {x['outcome'].upper()} | {x['E']} | {x['V']} |" for x in h)
    rounds = "\n".join(
        f"| {r['round']} | {r['idea'][:70]} | {len(r['sources'])} | {len(r['verified_claims_at_capture'])} | "
        f"{r['synthesis_mode']} | {r['evidence_score_at_capture']} |" for r in snap["rounds"])
    return f"""# Phase 1 — Evidence REPLAY check: {snap['label']}

> This run used **replayed** evidence from `{snap['_file']}`. Nothing was fetched: the snapshot holds the
> sources a live run collected on **{snap['captured_at']}** (original URLs, passages, fetch times, SHA-256).
> Verification, scoring and all gates were re-computed from that snapshot with the current code.
> Replay reproduces the *decisions*; it does not make the captured evidence stronger or fresher.
> Check the relevance of each verified claim in the research-findings file of this scenario.

**Reproduce:** `python orchestrator.py replay {snap['_file']} --scoring {scoring}`

## Captured research rounds

| Round | Idea researched | New sources | Verified claims at capture | Synthesis | E at capture |
|---|---|---|---|---|---|
{rounds}

**Captured under {captured_v}:** {_outcome_line(snap['gate_outcomes_at_capture'])}

**Replayed under {scoring}:** {_outcome_line(replayed)}{(' (run ' + run['status'] + ': ' + run['error'] + ')') if run.get('error') else ''}

## Gate outcomes: capture vs. this replay — {'MATCH' if match else ('SCORING-VERSION DIFFERENCE: expected when the relevance rule changes, not a failure' if scoring != captured_v else 'DIFFERENT')}

At capture (live run `{snap['captured_from_run']}`, final status {snap['final_status_at_capture']}):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
{rows(snap['gate_outcomes_at_capture'])}

This replay (final status {run['status']}):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
{rows(replayed)}
"""


# Demo scenarios: run id -> (brief used for --live, committed snapshot replayed by default)
DEMO_SCENARIOS = {
    "demo-strong": (DEMO_BRIEF_STRONG, SNAPSHOTS / "strong_scenario.json"),
    "demo-weak": (DEMO_BRIEF_WEAK, SNAPSHOTS / "weak_scenario.json"),
    "demo-replay": (None, DEMO_SNAPSHOT),          # REPEAT -> GO; always replayed
    # Headline scenario: strong brief captured live under the stricter v2 relevance rule
    "demo-headline": (DEMO_BRIEF_STRONG, SNAPSHOTS / "strong_v2_scenario.json"),
}


class SnapshotMissingError(RuntimeError):
    """A committed evidence snapshot the demo needs is missing or unreadable."""


def check_demo_snapshots(live: bool = False) -> None:
    """Every snapshot the demo will replay must exist and parse. No silent fallback to live research.
    (The REPEAT -> GO scenario is replayed even with --live, so its snapshot is always required.)"""
    for rid, (brief, snap) in DEMO_SCENARIOS.items():
        if live and brief:
            continue
        if not snap.exists():
            raise SnapshotMissingError(f"snapshot missing: {snap}; run `python orchestrator.py demo --live` "
                                       "for live research")
        try:
            loaded = load_snapshot(snap)
            if not loaded.get("rounds") or "gate_outcomes_at_capture" not in loaded:
                raise ValueError("no captured rounds or gate outcomes")
        except Exception as exc:
            raise SnapshotMissingError(f"snapshot unreadable: {snap} ({type(exc).__name__}: {exc}); "
                                       "run `python orchestrator.py demo --live` for live research") from exc


def run_demo(live: bool = False, log_path=None) -> dict:
    """Default: replay all three committed snapshots (reproducible, offline research).
    live=True: strong and weak scenarios do fresh live research instead (results vary run to run).
    Raises SnapshotMissingError before touching any run if a needed snapshot is missing/unreadable."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    check_demo_snapshots(live)
    db.init_db()
    results = {}
    for rid in DEMO_RUNS:
        _reset_run(rid)
    for rid, (brief, snap) in DEMO_SCENARIOS.items():
        if live and brief:
            print(f"[{rid}] LIVE research run…")
            run_sync(brief, rid, auto=True, evidence_cfg={"mode": "live", "capture": False})
            hist, match = _counters(rid)["history"], None
        else:
            shown = snap.relative_to(ROOT).as_posix() if snap.resolve().is_relative_to(ROOT) else snap
            print(f"[{rid}] REPLAY of {shown} (no network)…")
            res = replay(snap, rid)
            hist, match = res["replayed"], res["match"]
        run = db.get_run(rid)
        results[rid] = {"status": run["status"], "history": hist, "match": match}
        print(f"[{rid}] final status: {run['status']}  gates: "
              + " → ".join(f"G{h['gate']}:{h['outcome'].upper()}" for h in hist)
              + ("" if match is None else f"  (matches capture: {match})"))
    if not live:
        for rid, (brief, snap) in DEMO_SCENARIOS.items():
            if load_snapshot(snap).get("scoring_version", "v1") == "v2":
                continue                    # already captured and replayed under v2
            rid2 = f"{rid}-v2"
            res = replay(snap, rid2, scoring="v2")
            run = db.get_run(rid2)
            results[rid2] = {"status": run["status"], "history": res["replayed"], "match": res["match"],
                             "scoring_difference": res["scoring_difference"]}
            print(f"[{rid2}] scoring v2 replay: {run['status']}  gates: "
                  + (" → ".join(f"G{h['gate']}:{h['outcome'].upper()}" for h in res["replayed"]) or "none")
                  + (f"  ({run['error'][:90]})" if run.get("error") else ""))
    _demo_test_traffic("demo-strong")
    db.export_decision_log(str(log_path or ROOT / "decision_log.json"), run_ids=list(DEMO_RUNS))
    print("decision_log.json and outputs/ updated.")
    return results


def main(argv: list[str]) -> int:
    """CLI entry point; returns the process exit code."""
    args = argv
    if not args or args[0] in ("demo", "strong"):
        try:
            run_demo(live="--live" in args)
        except SnapshotMissingError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        return 0
    if args[0] == "run" and len(args) >= 2:
        logging.basicConfig(level=logging.WARNING)
        rid = secrets.token_hex(6)
        r = run_sync(args[1], rid, auto="--yes" in args)
        print(f"run {rid}: {r['status']} — outputs in {out_dir(rid)}")
        return 0
    if args[0] == "replay" and len(args) >= 2:
        logging.basicConfig(level=logging.WARNING)
        scoring = args[args.index("--scoring") + 1] if "--scoring" in args else None
        rest = [a for i, a in enumerate(args[2:], 2) if a != "--scoring" and args[i - 1] != "--scoring"]
        res = replay(args[1], rest[0] if rest else "demo-replay", scoring=scoring)
        print(f"captured under {res['captured_scoring']}: " + " → ".join(
            f"G{h['gate']}:{h['outcome'].upper()}" for h in res["captured"]))
        print(f"replayed under {res['scoring']}: " + (" → ".join(
            f"G{h['gate']}:{h['outcome'].upper()}" for h in res["replayed"]) or "none")
              + f" | final status: {res['run']['status']}"
              + (f" ({res['run']['error']})" if res["run"].get("error") else ""))
        if res["scoring_difference"]:
            print("scoring-version difference (labelled, not a failure)")
            return 0
        print(f"gate outcomes match capture: {res['match']}")
        if res["run"]["run_id"] in DEMO_RUNS:
            db.export_decision_log(str(ROOT / "decision_log.json"), run_ids=list(DEMO_RUNS))
        return 0 if res["match"] else 2
    if args[0] == "capture" and len(args) >= 3:
        logging.basicConfig(level=logging.WARNING)
        snap = capture(args[1], args[2])
        print(f"snapshot written to {args[2]}: gates "
              + " → ".join(f"G{h['gate']}:{h['outcome'].upper()}" for h in snap["gate_outcomes_at_capture"]))
        return 0
    if args[0] == "measure" and len(args) == 2:
        measure(args[1])
        print(f"Phase 6 re-measured — see {out_dir(args[1]) / out_name(args[1], 'phase6_step1_operate-memo.md')}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
