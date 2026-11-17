"""Smoke tests for gate logic — no API keys or network required."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models import ResearchFindings, Claim, Source, Critique, GateOutcome
from gates import guardrail_0, compute_evidence_score, evaluate_gate_1, evaluate_gate_2


# ---------------------------------------------------------------------------
# Guardrail 0
# ---------------------------------------------------------------------------

def test_guardrail_0_allows_valid_idea():
    blocked, reason = guardrail_0("An AI study planner for university students in Egypt")
    assert not blocked, reason


def test_guardrail_0_blocks_physical_goods():
    blocked, reason = guardrail_0("An e-commerce store selling physical goods")
    assert blocked
    assert "physical goods" in reason.lower()


def test_guardrail_0_blocks_crypto():
    blocked, reason = guardrail_0("A cryptocurrency trading platform")
    assert blocked


def test_guardrail_0_blocks_fake_reviews():
    blocked, reason = guardrail_0("An app that creates fake reviews for businesses")
    assert blocked


def test_guardrail_0_blocks_guaranteed_income():
    blocked, reason = guardrail_0("A system that provides guaranteed income to users")
    assert blocked


# ---------------------------------------------------------------------------
# Evidence Score
# ---------------------------------------------------------------------------

def _make_findings(n_claims=5, n_verified=3, n_domains=3, n_sources=3):
    categories = ["demand", "competitors", "pricing", "local_constraints", "channels"]
    claims = [
        Claim(category=categories[i % len(categories)],
              text=f"claim {i}", verified=(i < n_verified), is_assumption=(i >= n_verified))
        for i in range(n_claims)
    ]
    sources = [
        Source(key=f"S{i+1}", url=f"https://domain{i+1}.com/page",
               title=f"Source {i+1}", domain=f"domain{i+1}.com",
               fetch_time="2026-01-01T00:00:00Z",
               text_hash="abc", passages=["some text"])
        for i in range(n_sources)
    ]
    return ResearchFindings(claims=claims, sources=sources[:n_domains])


def test_evidence_score_all_categories_some_verified():
    findings = _make_findings(n_claims=5, n_verified=3, n_domains=3)
    score = compute_evidence_score(findings)
    assert 40 < score < 100, f"Expected moderate score, got {score}"


def test_evidence_score_zero_sources():
    findings = ResearchFindings(claims=[], sources=[])
    score = compute_evidence_score(findings)
    assert score == 0.0


def test_evidence_score_max():
    findings = _make_findings(n_claims=5, n_verified=5, n_domains=5)
    score = compute_evidence_score(findings)
    assert score > 70


# ---------------------------------------------------------------------------
# Gate 1
# ---------------------------------------------------------------------------

def test_gate_1_go_on_strong_evidence():
    findings = _make_findings(n_claims=5, n_verified=3, n_domains=5)
    findings.evidence_score = compute_evidence_score(findings)
    result = evaluate_gate_1(findings)
    assert result.outcome == GateOutcome.GO, f"Expected GO but got {result.outcome}: {result.reason}"


def test_gate_1_stop_on_weak_evidence():
    findings = ResearchFindings(
        claims=[Claim(category="demand", text="x", is_assumption=True)],
        sources=[],
    )
    result = evaluate_gate_1(findings)
    assert result.outcome == GateOutcome.STOP, f"Expected STOP but got {result.outcome}"
    assert result.evidence_score < 25


def test_gate_1_repeat_on_medium_evidence():
    # 2 categories covered, 1 verified, 1 domain — should produce REPEAT or STOP, not GO
    findings = _make_findings(n_claims=2, n_verified=1, n_domains=1)
    findings.evidence_score = compute_evidence_score(findings)
    result = evaluate_gate_1(findings)
    assert result.outcome in (GateOutcome.REPEAT, GateOutcome.STOP)


# ---------------------------------------------------------------------------
# Gate 2
# ---------------------------------------------------------------------------

def test_gate_2_go_on_strong_scores():
    findings = _make_findings(n_claims=5, n_verified=3, n_domains=5)
    findings.evidence_score = 65.0
    critique = Critique(
        summary="Good",
        evidence_score=65.0,
        viability_score=3.8,
        recommendation=GateOutcome.GO,
        unresolved_kill_assumptions=0,
    )
    result = evaluate_gate_2(findings, critique)
    assert result.outcome == GateOutcome.GO, result.reason


def test_gate_2_stop_on_low_viability():
    findings = _make_findings()
    findings.evidence_score = 60.0
    critique = Critique(
        summary="Weak",
        evidence_score=60.0,
        viability_score=1.2,  # below hard-stop threshold
        recommendation=GateOutcome.STOP,
        unresolved_kill_assumptions=2,
    )
    result = evaluate_gate_2(findings, critique)
    assert result.outcome == GateOutcome.STOP
