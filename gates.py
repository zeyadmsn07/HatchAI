"""Gate logic — all scoring and decisions are deterministic Python.

No LLM can approve or block a run. Gate 0 is fail-closed.
Thresholds live in config/gates.yaml so they can be tuned without code changes.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

import yaml

from models import GateOutcome, GateResult, ResearchFindings, Critique

_CFG: dict = {}


def _cfg() -> dict:
    global _CFG
    if not _CFG:
        path = Path(__file__).parent / "config" / "gates.yaml"
        with open(path, encoding="utf-8") as f:
            _CFG = yaml.safe_load(f)
    return _CFG


# ---------------------------------------------------------------------------
# Guardrail 0 — fail-closed, no override
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"\s+", " ", text)
    return text


def guardrail_0(text: str) -> tuple[bool, str]:
    """Return (is_blocked, reason). Fail-closed: errors block."""
    cfg = _cfg()
    norm = _normalise(text)

    for term in cfg.get("excluded_terms", []):
        if term.lower() in norm:
            return True, f"Excluded category or product type: '{term}'"

    for phrase in cfg.get("trick_intents", []):
        if phrase.lower() in norm:
            return True, f"Prohibited intent detected: '{phrase}'"

    return False, ""


# ---------------------------------------------------------------------------
# Evidence Score (0–100)
# ---------------------------------------------------------------------------

def compute_evidence_score(findings: ResearchFindings) -> float:
    cfg = _cfg().get("evidence_score", {})
    cat_w = cfg.get("category_weight", 40)
    ver_w = cfg.get("verified_ratio_weight", 25)
    dom_w = cfg.get("domain_diversity_weight", 20)
    rec_w = cfg.get("recency_weight", 15)
    max_dom = cfg.get("max_domains", 5)

    all_categories = {"demand", "competitors", "pricing", "local_constraints", "channels"}
    covered = {c.category for c in findings.claims if c.category in all_categories}
    cat_score = cat_w * (len(covered) / len(all_categories))

    total = len(findings.claims)
    verified = sum(1 for c in findings.claims if c.verified and not c.is_assumption)
    ver_score = ver_w * (verified / total) if total else 0

    domains = len({s.domain for s in findings.sources})
    dom_score = dom_w * (min(domains, max_dom) / max_dom)

    # Sources with fetch_time within ~24 months counted as recent
    recent = sum(1 for s in findings.sources if "2024" in s.fetch_time or "2025" in s.fetch_time or "2026" in s.fetch_time)
    total_src = len(findings.sources) or 1
    rec_score = rec_w * (recent / total_src)

    return round(cat_score + ver_score + dom_score + rec_score, 1)


# ---------------------------------------------------------------------------
# Viability Score (1–5) — normally set by validator; we floor/cap it here
# ---------------------------------------------------------------------------

def clamp_viability(v: float) -> float:
    return max(1.0, min(5.0, round(v, 2)))


# ---------------------------------------------------------------------------
# Gate 1 — end of Phase 1
# ---------------------------------------------------------------------------

def evaluate_gate_1(findings: ResearchFindings) -> GateResult:
    cfg = _cfg()["gate_1"]
    e = compute_evidence_score(findings)
    findings.evidence_score = e

    checks = {
        "evidence_score_above_go": e >= cfg["evidence_score_go"],
        "evidence_score_above_stop": e >= cfg["evidence_score_stop"],
        "distinct_domains_ok": len({s.domain for s in findings.sources}) >= cfg["min_distinct_domains"],
        "target_market_set": not any(
            "ASSUMPTION" in c.text and c.category == "local_constraints"
            for c in findings.claims
        ),
        "geography_set": True,
    }

    if e < cfg["evidence_score_stop"]:
        return GateResult(
            gate_id=1,
            outcome=GateOutcome.STOP,
            evidence_score=e,
            reason=f"Evidence score {e} is below the STOP threshold {cfg['evidence_score_stop']}. "
                   "Insufficient evidence to proceed — recommend abandoning this idea.",
            checks=checks,
        )

    if e < cfg["evidence_score_go"] or not checks["distinct_domains_ok"]:
        return GateResult(
            gate_id=1,
            outcome=GateOutcome.REPEAT,
            evidence_score=e,
            reason=f"Evidence score {e} is below GO threshold {cfg['evidence_score_go']} "
                   f"or domain diversity < {cfg['min_distinct_domains']}. "
                   "Recommend one more research round.",
            checks=checks,
        )

    return GateResult(
        gate_id=1,
        outcome=GateOutcome.GO,
        evidence_score=e,
        reason=f"Evidence score {e} ≥ {cfg['evidence_score_go']} and domain diversity satisfied.",
        checks=checks,
    )


# ---------------------------------------------------------------------------
# Gate 2 — end of Phase 2
# ---------------------------------------------------------------------------

def evaluate_gate_2(findings: ResearchFindings, critique: Critique) -> GateResult:
    cfg = _cfg()["gate_2"]
    e = findings.evidence_score
    v = clamp_viability(critique.viability_score)
    unresolved = critique.unresolved_kill_assumptions

    checks = {
        "evidence_score_ok": e >= cfg["evidence_score_go"],
        "viability_score_ok": v >= cfg["viability_score_go"],
        "no_unresolved_kills": unresolved <= cfg["max_unresolved_kill_assumptions"],
    }

    hard_stops = []
    if e < cfg["evidence_score_stop"]:
        hard_stops.append(f"E={e} < hard-stop threshold {cfg['evidence_score_stop']}")
    if v < cfg["viability_score_stop"]:
        hard_stops.append(f"V={v} < hard-stop threshold {cfg['viability_score_stop']}")
    if unresolved > 0:
        hard_stops.append(f"{unresolved} unresolved kill assumption(s) remain")

    if hard_stops:
        return GateResult(
            gate_id=2,
            outcome=GateOutcome.STOP,
            evidence_score=e,
            viability_score=v,
            reason="Hard-stop rules triggered: " + "; ".join(hard_stops),
            checks=checks,
        )

    if not checks["evidence_score_ok"] or not checks["viability_score_ok"]:
        return GateResult(
            gate_id=2,
            outcome=GateOutcome.REPEAT,
            evidence_score=e,
            viability_score=v,
            reason=f"E={e} or V={v} below GO thresholds. Recommend one retry.",
            checks=checks,
        )

    return GateResult(
        gate_id=2,
        outcome=GateOutcome.GO,
        evidence_score=e,
        viability_score=v,
        reason=f"E={e} ≥ {cfg['evidence_score_go']}, V={v} ≥ {cfg['viability_score_go']}, "
               "no unresolved kill assumptions.",
        checks=checks,
    )


# ---------------------------------------------------------------------------
# Gates 3–5 — structural checks only
# ---------------------------------------------------------------------------

def evaluate_gate_3(mvp_spec: str) -> GateResult:
    required_sections = ["## User Stories", "## Scope", "## Stack", "## Out of Scope"]
    checks = {f"has_{s.strip('# ').lower().replace(' ', '_')}": s in mvp_spec
              for s in required_sections}
    all_pass = all(checks.values())
    return GateResult(
        gate_id=3,
        outcome=GateOutcome.GO if all_pass else GateOutcome.REPEAT,
        reason="All PRD sections present." if all_pass else "Missing required PRD sections.",
        checks=checks,
    )


def evaluate_gate_4(pricing: str, policies: str) -> GateResult:
    cfg = _cfg()["gate_4"]
    checks = {
        "pricing": bool(pricing),
        "terms": "Terms" in policies,
        "privacy": "Privacy" in policies,
        "refund_policy": "Refund" in policies,
    }
    all_pass = all(checks.values())
    return GateResult(
        gate_id=4,
        outcome=GateOutcome.GO if all_pass else GateOutcome.STOP,
        reason="All commercial documents present." if all_pass else "Missing pricing or policy document.",
        checks=checks,
    )


def evaluate_gate_5(payment_log: str) -> GateResult:
    checks = {
        "idempotency_pass": "IDEMPOTENCY: PASS" in payment_log,
        "revocation_pass": "REVOCATION: PASS" in payment_log,
        "reconciliation_pass": "RECONCILIATION: PASS" in payment_log,
    }
    all_pass = all(checks.values())
    return GateResult(
        gate_id=5,
        outcome=GateOutcome.GO if all_pass else GateOutcome.STOP,
        reason="Sale-to-Cash simulation passed." if all_pass else "Sale-to-Cash simulation failed.",
        checks=checks,
    )
