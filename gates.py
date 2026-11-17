"""Gate logic — all scoring and decisions are deterministic Python.

No LLM can approve or block a run. Guardrail 0 is fail-closed.
Thresholds live in config/gates.yaml.

Outcomes:
  GO      evidence/quality bar met — founder may approve the next phase
  REPEAT  close, but evidence/quality is short and a retry budget remains
  PIVOT   retries exhausted (or idea scores poorly) but a better-evidenced angle exists
  STOP    evidence too weak, brief undefined, or build/sale checks failed — don't launch this
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

import yaml

from models import Critique, FounderBrief, GateOutcome, GateResult, KillAssumption, ResearchFindings

_CFG: dict = {}
CATEGORIES = ("demand", "competitors", "pricing", "local_constraints", "channels")


def _cfg() -> dict:
    global _CFG
    if not _CFG:
        with open(Path(__file__).parent / "config" / "gates.yaml", encoding="utf-8") as f:
            _CFG = yaml.safe_load(f)
    return _CFG


# ---------------------------------------------------------------------------
# Guardrail 0 — fail-closed, no override; also used as an output scanner
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", text)


def guardrail_0(text: str) -> tuple[bool, str]:
    """Return (is_blocked, reason). Fail-closed: errors block."""
    try:
        cfg = _cfg()
        norm = _normalise(text)
        for term in cfg.get("excluded_terms", []):
            if re.search(rf"\b{re.escape(term.lower())}\b", norm):
                return True, f"Excluded category or product type: '{term}'"
        for phrase in cfg.get("trick_intents", []):
            if phrase.lower() in norm:
                return True, f"Prohibited intent detected: '{phrase}'"
        return False, ""
    except Exception as exc:  # fail closed
        return True, f"Guardrail error (fail-closed): {exc}"


def scan_output(text: str) -> list[str]:
    """Return forbidden phrases found in a generated artifact (income promises, fake urgency...)."""
    norm = _normalise(text)
    return [p for p in _cfg().get("forbidden_output_phrases", []) if p.lower() in norm]


# ---------------------------------------------------------------------------
# Evidence Score (0–100) — only verified, quoted claims count
# ---------------------------------------------------------------------------

def _cited_sources(findings: ResearchFindings):
    keys = {k for c in findings.claims if c.verified and not c.is_assumption for k in c.source_keys}
    return [s for s in findings.sources if s.key in keys]


def evidence_breakdown(findings: ResearchFindings) -> dict[str, float]:
    cfg = _cfg()["evidence_score"]
    verified = [c for c in findings.claims if c.verified and not c.is_assumption]
    covered = {c.category for c in verified if c.category in CATEGORIES}
    total = len(findings.claims)
    cited = _cited_sources(findings)
    domains = {s.domain for s in cited}
    types = {(s.collector or "web").split(":")[0] for s in cited}
    return {
        "category_coverage": round(cfg["category_weight"] * len(covered) / len(CATEGORIES), 1),
        "verified_ratio": round(cfg["verified_ratio_weight"] * (len(verified) / total if total else 0), 1),
        "domain_diversity": round(cfg["domain_diversity_weight"] * min(len(domains), cfg["max_domains"]) / cfg["max_domains"], 1),
        "source_type_triangulation": round(cfg["source_type_weight"] * min(len(types), 3) / 3, 1),
    }


def compute_evidence_score(findings: ResearchFindings) -> float:
    return round(sum(evidence_breakdown(findings).values()), 1)


def verified_categories(findings: ResearchFindings) -> set[str]:
    return {c.category for c in findings.claims if c.verified and not c.is_assumption}


# ---------------------------------------------------------------------------
# Viability Score (1–5) — computed from evidence + founder fit, never by an LLM
# ---------------------------------------------------------------------------

_BUILD_SKILLS = ("develop", "programm", "python", "javascript", "web", "software", "code", "coding",
                 "engineer", "design", "no-code", "nocode", "data", "full-stack", "fullstack")


def compute_viability(findings: ResearchFindings, brief: FounderBrief,
                      risks: Iterable[KillAssumption] = ()) -> tuple[float, dict[str, float]]:
    cats = verified_categories(findings)
    skills = (brief.skills or "").lower()
    risks = list(risks)
    b = {
        "base": 1.0,
        "demand_verified": 1.0 if "demand" in cats else 0.0,
        "competitors_verified": 0.5 if "competitors" in cats else 0.0,
        "pricing_verified": 0.5 if "pricing" in cats else 0.0,
        "local_constraints_verified": 0.5 if "local_constraints" in cats else 0.0,
        "founder_skills": 0.5 if "skills" not in brief.unknown_fields and any(k in skills for k in _BUILD_SKILLS) else 0.0,
        "founder_time": 0.25 if "hours_per_week" not in brief.unknown_fields and brief.hours_per_week >= 5 else 0.0,
        "risks_testable": 0.25 if risks and all(r.kill_criterion for r in risks) else 0.0,
        # Willingness to pay is only proven by the pre-registered demand test (Phase 6);
        # before launch this is always 0, so pre-launch viability tops out at 4.5.
        "demand_test_passed": 0.0,
    }
    return clamp_viability(sum(b.values())), b


def clamp_viability(v: float) -> float:
    return max(1.0, min(5.0, round(v, 2)))


def _brief_undefined(brief: FounderBrief | None) -> bool:
    return bool(brief) and {"target_user", "geography"} <= set(brief.unknown_fields)


# ---------------------------------------------------------------------------
# Gate 1 — end of Phase 1 (Discover)
# ---------------------------------------------------------------------------

def evaluate_gate_1(findings: ResearchFindings, brief: FounderBrief | None = None,
                    round_no: int = 1, pivots_used: int = 0) -> GateResult:
    cfg = _cfg()["gate_1"]
    e = compute_evidence_score(findings)
    findings.evidence_score = e
    cats = verified_categories(findings)
    domains = len({s.domain for s in _cited_sources(findings)})
    can_repeat = round_no < cfg["max_research_rounds"]
    can_pivot = pivots_used < cfg["max_pivots"] and bool(findings.opportunity_angles)

    checks = {
        "brief_defines_target_user_and_geography": not _brief_undefined(brief),
        "evidence_score_at_least_go": e >= cfg["evidence_score_go"],
        "evidence_score_above_stop": e >= cfg["evidence_score_stop"],
        "demand_evidence_verified": "demand" in cats,
        f"cited_domains_at_least_{cfg['min_distinct_domains']}": domains >= cfg["min_distinct_domains"],
    }
    detail = f"E={e} (GO ≥ {cfg['evidence_score_go']}, STOP < {cfg['evidence_score_stop']}); " \
             f"verified categories: {sorted(cats) or 'none'}; cited domains: {domains}; research round {round_no}."

    def result(outcome, reason, pivot_to=""):
        return GateResult(gate_id=1, outcome=outcome, evidence_score=e, reason=f"{reason} {detail}",
                          checks=checks, pivot_to=pivot_to)

    if _brief_undefined(brief):
        return result(GateOutcome.STOP, "STOP: the brief names neither a target user nor a geography, so "
                      "no market can be validated. Resubmit with a specific user and country.")
    if e < cfg["evidence_score_stop"] and not can_repeat:
        return result(GateOutcome.STOP, "STOP: evidence remains below the stop threshold after the retry budget.")
    passed = all(checks.values())
    if passed:
        return result(GateOutcome.GO, "GO: enough verified, diverse evidence to start validation.")
    if can_repeat:
        return result(GateOutcome.REPEAT, "REPEAT: evidence is incomplete — run another, broader research round.")
    if can_pivot and e >= cfg["evidence_score_stop"]:
        return result(GateOutcome.PIVOT, "PIVOT: retries exhausted without meeting GO; refocus on the "
                      "best-evidenced opportunity angle.", findings.opportunity_angles[0])
    return result(GateOutcome.STOP, "STOP: evidence did not reach GO within the retry and pivot budget.")


# ---------------------------------------------------------------------------
# Gate 2 — end of Phase 2 (Validate)
# ---------------------------------------------------------------------------

def evaluate_gate_2(findings: ResearchFindings, critique: Critique, round_no: int = 1,
                    pivots_used: int = 0) -> GateResult:
    cfg = _cfg()["gate_2"]
    e = compute_evidence_score(findings)
    v = clamp_viability(critique.viability_score)
    unresolved = critique.unresolved_kill_assumptions
    can_pivot = pivots_used < _cfg()["gate_1"]["max_pivots"] and bool(findings.opportunity_angles)

    checks = {
        "evidence_score_ok": e >= cfg["evidence_score_go"],
        "viability_score_ok": v >= cfg["viability_score_go"],
        "every_high_risk_assumption_has_kill_criterion": unresolved <= cfg["max_unresolved_kill_assumptions"],
        "demand_test_pre_registered": True,
    }
    detail = f"E={e} (GO ≥ {cfg['evidence_score_go']}), V={v} (GO ≥ {cfg['viability_score_go']}), " \
             f"V breakdown: {critique.viability_breakdown}."

    def result(outcome, reason, pivot_to=""):
        return GateResult(gate_id=2, outcome=outcome, evidence_score=e, viability_score=v,
                          reason=f"{reason} {detail}", checks=checks, pivot_to=pivot_to)

    if e < cfg["evidence_score_stop"] or v < cfg["viability_score_stop"]:
        return result(GateOutcome.STOP, "STOP: hard-stop threshold hit — weak evidence or low viability.")
    if all(checks.values()):
        return result(GateOutcome.GO, "GO: evidence and viability clear the bar; build the MVP to run the demand test.")
    if not checks["viability_score_ok"] and checks["evidence_score_ok"] and can_pivot:
        return result(GateOutcome.PIVOT, "PIVOT: the market evidence is real but this idea scores low on "
                      "viability; refocus on the best-evidenced angle.", findings.opportunity_angles[0])
    if round_no < _cfg()["gate_1"]["max_research_rounds"]:
        return result(GateOutcome.REPEAT, "REPEAT: gather one more research round before building.")
    return result(GateOutcome.STOP, "STOP: validation bar not met within the retry budget.")


# ---------------------------------------------------------------------------
# Gate 3 — generated MVP must pass its own tests
# ---------------------------------------------------------------------------

def evaluate_gate_3(build_report: dict, attempt: int = 1) -> GateResult:
    cfg = _cfg()["gate_3"]
    t = build_report.get("tests", {})
    if build_report.get("supported") is False:
        # Deterministic: rebuilding cannot help, so no REPEAT. The founder may still
        # override with a written reason (continues without an MVP) or stop.
        checks = {"tested_template_fits_idea": False, "mvp_files_generated": False,
                  "generated_tests_ran": False, "server_smoke_test_pass": False}
        return GateResult(gate_id=3, outcome=GateOutcome.STOP, checks=checks,
                          reason="STOP: no MVP was built. " + build_report.get("unsupported_reason", "")
                          + " A spec-only document (STUBBED) was written instead.")
    checks = {
        "mvp_files_generated": build_report.get("files", 0) > 0,
        "generated_tests_ran": t.get("ran", 0) >= cfg["min_tests"],
        "all_generated_tests_pass": t.get("ran", 0) > 0 and t.get("failed", 1) == 0 and t.get("errors", 1) == 0,
        "every_feature_traced_to_problem": build_report.get("features_traced", False),
        "server_smoke_test_pass": build_report.get("smoke_ok", False),
        "no_forbidden_phrases": not build_report.get("forbidden_phrases"),
    }
    summary = (f"{t.get('ran', 0)} generated tests ran, {t.get('failed', '?')} failed, "
               f"{t.get('errors', '?')} errors (attempt {attempt}).")
    if all(checks.values()):
        outcome, reason = GateOutcome.GO, f"GO: runnable MVP built and verified. {summary}"
    elif attempt < cfg["max_build_attempts"]:
        outcome, reason = GateOutcome.REPEAT, f"REPEAT: MVP did not pass verification; rebuild. {summary}"
    else:
        outcome, reason = GateOutcome.STOP, f"STOP: MVP failed verification after retries. {summary}"
    return GateResult(gate_id=3, outcome=outcome, reason=reason, checks=checks)


# ---------------------------------------------------------------------------
# Gates 4–5
# ---------------------------------------------------------------------------

def evaluate_gate_4(pricing: str, policies: str) -> GateResult:
    forbidden = scan_output(pricing + policies)
    checks = {
        "pricing": "## Tiers" in pricing,
        "free_core_tier": "Free" in pricing,
        "terms": "Terms" in policies,
        "privacy": "Privacy" in policies,
        "refund_policy": "Refund" in policies,
        "not_legal_advice_label": "not legal advice" in policies.lower(),
        "no_income_promises": not forbidden,
    }
    ok = all(checks.values())
    return GateResult(gate_id=4, outcome=GateOutcome.GO if ok else GateOutcome.STOP,
                      reason="GO: pricing and policy drafts complete and labelled." if ok else
                      f"STOP: commercial documents incomplete or contain forbidden claims {forbidden}.",
                      checks=checks)


def evaluate_gate_5(payment_log: str, launch_drafts: str = "") -> GateResult:
    checks = {
        "idempotency_pass": "IDEMPOTENCY: PASS" in payment_log,
        "revocation_pass": "REVOCATION: PASS" in payment_log,
        "reconciliation_pass": "RECONCILIATION: PASS" in payment_log,
        "launch_drafts_held_for_approval": "PENDING_FOUNDER_APPROVAL" in launch_drafts if launch_drafts else True,
        "no_forbidden_phrases_in_drafts": not scan_output(launch_drafts),
    }
    ok = all(checks.values())
    return GateResult(gate_id=5, outcome=GateOutcome.GO if ok else GateOutcome.STOP,
                      reason="GO: sale-to-cash simulation passed; launch drafts held for approval." if ok else
                      "STOP: sale-to-cash simulation or launch-draft checks failed.", checks=checks)
