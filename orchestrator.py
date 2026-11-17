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
  python orchestrator.py demo                 # committed demo: strong idea (full run) + weak idea (STOP)
  python orchestrator.py run "<brief>"        # interactive: you approve each gate at the prompt
  python orchestrator.py run "<brief>" --yes  # follow every gate recommendation automatically
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
DEMO_RUNS = {"demo-strong": "", "demo-weak": "-weak-idea"}

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
    if not suffix or filename == "payment_test_log.md":
        return filename
    stem, _, ext = filename.rpartition(".")
    return f"{stem}{suffix}.{ext}"


def _write(run_id: str, filename: str, content: str) -> pathlib.Path:
    path = out_dir(run_id) / out_name(run_id, filename)
    path.write_text(content, encoding="utf-8")
    return path


def list_outputs(run_id: str) -> list[pathlib.Path]:
    d = out_dir(run_id)
    suffix = DEMO_RUNS.get(run_id)
    files = sorted(p for p in d.iterdir() if p.is_file())
    if suffix is None:
        return files
    if suffix:
        return [p for p in files if suffix in p.name]
    return [p for p in files if not any(s and s in p.name for s in DEMO_RUNS.values())]


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

def start_run(brief_text: str, run_id: str | None = None, auto_approve: bool = False) -> str:
    db.init_db()
    run_id = run_id or secrets.token_hex(8)
    db.create_run(run_id, secrets.token_hex(16), json.dumps({"raw": brief_text}),
                  datetime.now(timezone.utc).isoformat(), auto_approve=auto_approve)
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
        findings = research_run(run_id, brief, round_no=c["round"], previous=previous)
        gate = gates.evaluate_gate_1(findings, brief, round_no=c["round"], pivots_used=c["pivots"])
        _store(run_id, "findings", findings)

        _write(run_id, "phase1_step1_intake.md", _format_brief(brief))
        _write(run_id, "phase1_step2_research-findings.md", _format_findings(findings))
        _write(run_id, "phase1_step3_sources.json", json.dumps(
            [s.model_dump() for s in findings.sources], indent=2, ensure_ascii=False))
        _gate(run_id, gate, 1)
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

        report = build_run(run_id, brief, canvas, critique, attempt=c["build_attempt"])
        gate = gates.evaluate_gate_3(report, attempt=c["build_attempt"])
        if not report.get("supported", True):
            # No template fits: write a spec-only document; never claim an MVP exists.
            _store(run_id, "app", {"supported": False, "reason": report["unsupported_reason"]})
            _write(run_id, "phase3_step1_mvp-spec.md", _format_unsupported_spec(report, brief, canvas, critique))
            _gate(run_id, gate, 3)
            return
        _store(run_id, "app", {"product_name": report["spec"].product_name, "app_dir": str(report["app_dir"]),
                               "archetype": report["spec"].archetype, "supported": True})

        _write(run_id, "phase3_step1_mvp-spec.md", _format_mvp_spec(report, canvas))
        _write(run_id, "phase3_step2_mvp-source.md", _format_mvp_source(report))
        _write(run_id, "phase3_step3_mvp-test-report.txt", _format_test_report(report))
        _gate(run_id, gate, 3)
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
        co = checkout(run_id, amount_egp=amount)
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

        brief = _load(run_id, "brief", FounderBrief)
        dt = _load(run_id, "demand_test", DemandTest)
        app = _load(run_id, "app", default={})
        memo = operate_run(run_id, brief, dt, pathlib.Path(app["app_dir"]) if app.get("app_dir") else None,
                           _load(run_id, "payment", default={}))
        _write(run_id, "phase6_step1_operate-memo.md", memo)
        db.update_run_status(run_id, "completed", phase=6)
        callbacks.log(run_id, "orchestrator", "run_completed", phase=6, outcome="completed")
    except Exception as exc:
        _fail(run_id, 6, exc)


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
    by_key = {s.key: s for s in f.sources}
    lines = []
    for c in f.claims:
        cites = ", ".join(f"[{k}]({by_key[k].url})" for k in c.source_keys if k in by_key)
        tag = f"VERIFIED — {cites}" if c.verified else "**ASSUMPTION**"
        lines.append(f"- **{c.category}** — {c.text} ({tag})")
    breakdown = gates.evidence_breakdown(f)
    return f"""# Phase 1 — Research findings (round {f.research_round})

> Synthesis mode: **{f.mode}** ({'open-weight LLM, quotes re-verified by code' if f.mode == 'llm' else 'no LLM: claims are verbatim passages from fetched sources'}).
> Every claim cites a fetched source whose text contains the quoted passage, or is labelled ASSUMPTION.

## Claims

{chr(10).join(lines)}

## Opportunity angles

{chr(10).join(f"- {a}" for a in f.opportunity_angles)}

## Evidence score: {gates.compute_evidence_score(f)} / 100

| Component | Points |
|---|---|
{chr(10).join(f"| {k.replace('_', ' ')} | {v} |" for k, v in breakdown.items())}

## Source ledger ({len(f.sources)} sources, {len({s.domain for s in f.sources})} domains)

{chr(10).join(f"- `{s.key}` [{s.title}]({s.url}) — {s.collector}, {s.category}, fetched {s.fetch_time}, sha256:{s.text_hash}" for s in f.sources) or "- none fetched"}
"""


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


def _reset_run(run_id: str):
    import shutil
    shutil.rmtree(RUNS / run_id, ignore_errors=True)
    with db.get_conn() as conn:
        for t in ("gate_results", "decision_log", "runs"):
            conn.execute(f"DELETE FROM {t} WHERE run_id=?", (run_id,))
    for p in OUTPUTS.glob("*"):
        if run_id in DEMO_RUNS and p.is_file() and p in list_outputs(run_id):
            p.unlink()


def run_sync(brief_text: str, run_id: str, auto: bool = True, interactive: bool = True) -> dict:
    """Run a full pipeline in this thread (CLI/demo). Returns the final run row."""
    db.init_db()
    _mode.sync = True
    try:
        start_run(brief_text, run_id=run_id, auto_approve=auto)
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


def run_demo():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    db.init_db()
    for rid in DEMO_RUNS:
        _reset_run(rid)
    for rid, brief in (("demo-strong", DEMO_BRIEF_STRONG), ("demo-weak", DEMO_BRIEF_WEAK)):
        print(f"[{rid}] running…")
        run = run_sync(brief, rid, auto=True)
        hist = _counters(rid)["history"]
        print(f"[{rid}] final status: {run['status']}  gates: "
              + " → ".join(f"G{h['gate']}:{h['outcome'].upper()}" for h in hist))
    db.export_decision_log(str(ROOT / "decision_log.json"), run_ids=list(DEMO_RUNS))
    print("decision_log.json and outputs/ updated.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("demo", "strong"):
        run_demo()
    elif args[0] == "run" and len(args) >= 2:
        logging.basicConfig(level=logging.WARNING)
        rid = secrets.token_hex(6)
        r = run_sync(args[1], rid, auto="--yes" in args)
        print(f"run {rid}: {r['status']} — outputs in {out_dir(rid)}")
    else:
        print(__doc__)
        sys.exit(1)
