"""Gate logic: Guardrail 0, evidence/viability scoring, GO / REPEAT / PIVOT / STOP."""
from tests.conftest import STRONG, make_sources

from gates import (compute_evidence_score, compute_viability, evaluate_gate_1, evaluate_gate_2, evaluate_gate_3,
                   evaluate_gate_4, evaluate_gate_5, guardrail_0, scan_output)
from models import Claim, Critique, FounderBrief, GateOutcome, KillAssumption, ResearchFindings

BRIEF = FounderBrief(idea="flashcards", target_user="students", geography="Egypt", skills="web development",
                     hours_per_week=10)
WEAK_BRIEF = FounderBrief(idea="notes", unknown_fields=["target_user", "geography", "skills", "hours_per_week"])


def findings_for(categories, n_domains=5, angles=("Narrow to STEM students",)):
    spec = {c: STRONG[c] for c in categories}
    sources = make_sources(spec)
    claims = [Claim(category=s.category, text=s.passages[0], source_keys=[s.key], quote=s.passages[0],
                    verified=True) for s in sources]
    for c in set(STRONG) - set(categories):
        claims.append(Claim(category=c, text=f"ASSUMPTION: {c}", is_assumption=True))
    return ResearchFindings(claims=claims, sources=sources[:n_domains], opportunity_angles=list(angles))


# Guardrail 0 -------------------------------------------------------------

def test_guardrail_allows_valid_idea():
    assert guardrail_0("An AI study planner for university students in Egypt") == (False, "")


def test_guardrail_blocks_excluded_categories_and_trick_intents():
    for text in ("A store selling physical goods", "A cryptocurrency trading bot", "Generate fake reviews for shops",
                 "Guaranteed income for subscribers", "Impersonate a famous brand", "medical advice chatbot"):
        assert guardrail_0(text)[0], text


def test_output_scanner_flags_income_promises():
    assert scan_output("Join now — guaranteed income in 30 days!") == ["guaranteed income"]
    assert scan_output("An early, free MVP. Feedback welcome.") == []


# Scores --------------------------------------------------------------------

def test_evidence_score_counts_only_verified_claims():
    full = findings_for(list(STRONG))
    assert compute_evidence_score(full) > 85
    unverified = ResearchFindings(claims=[Claim(category=c, text="ASSUMPTION", is_assumption=True) for c in STRONG])
    assert compute_evidence_score(unverified) == 0.0


def test_viability_is_computed_from_evidence_and_founder_fit():
    risks = [KillAssumption(assumption="pay", kill_criterion="<3% click price")]
    v_strong, b = compute_viability(findings_for(list(STRONG)), BRIEF, risks)
    v_weak, _ = compute_viability(findings_for([]), WEAK_BRIEF, [])
    assert v_strong == 4.5 and b["founder_skills"] == 0.5 and b["demand_test_passed"] == 0.0
    assert v_weak == 1.0


# Gate 1 ---------------------------------------------------------------------

def test_gate1_go_with_strong_verified_evidence():
    g = evaluate_gate_1(findings_for(list(STRONG)), BRIEF)
    assert g.outcome == GateOutcome.GO, g.reason


def test_gate1_stop_when_brief_has_no_user_or_geography():
    g = evaluate_gate_1(findings_for(list(STRONG)), WEAK_BRIEF)
    assert g.outcome == GateOutcome.STOP
    assert "neither a target user nor a geography" in g.reason


def test_gate1_repeat_then_pivot_then_stop_as_budgets_run_out():
    mid = findings_for(["demand", "competitors"], n_domains=2)
    assert evaluate_gate_1(mid, BRIEF, round_no=1).outcome == GateOutcome.REPEAT
    g = evaluate_gate_1(mid, BRIEF, round_no=2, pivots_used=0)
    assert g.outcome == GateOutcome.PIVOT and g.pivot_to == "Narrow to STEM students"
    assert evaluate_gate_1(mid, BRIEF, round_no=2, pivots_used=1).outcome == GateOutcome.STOP


def test_gate1_stop_on_no_evidence_after_retry():
    empty = findings_for([])
    assert evaluate_gate_1(empty, BRIEF, round_no=1).outcome == GateOutcome.REPEAT
    assert evaluate_gate_1(empty, BRIEF, round_no=2).outcome == GateOutcome.STOP


# Gate 2 ---------------------------------------------------------------------

def _critique(v, unresolved=0):
    return Critique(summary="s", viability_score=v, unresolved_kill_assumptions=unresolved)


def test_gate2_outcomes():
    strong = findings_for(list(STRONG))
    assert evaluate_gate_2(strong, _critique(4.0)).outcome == GateOutcome.GO
    assert evaluate_gate_2(strong, _critique(2.5)).outcome == GateOutcome.PIVOT
    assert evaluate_gate_2(strong, _critique(1.5)).outcome == GateOutcome.STOP
    assert evaluate_gate_2(findings_for(["demand", "competitors"], 2), _critique(4.0)).outcome == GateOutcome.REPEAT  # E=44
    assert evaluate_gate_2(strong, _critique(4.0, unresolved=1)).outcome == GateOutcome.REPEAT


# Gates 3–5 ------------------------------------------------------------------

def test_gate3_requires_passing_generated_tests():
    ok = {"files": 9, "tests": {"ran": 20, "failed": 0, "errors": 0}, "features_traced": True,
          "smoke_ok": True, "forbidden_phrases": []}
    assert evaluate_gate_3(ok).outcome == GateOutcome.GO
    bad = {**ok, "tests": {"ran": 20, "failed": 2, "errors": 0}}
    assert evaluate_gate_3(bad, attempt=1).outcome == GateOutcome.REPEAT
    assert evaluate_gate_3(bad, attempt=2).outcome == GateOutcome.STOP


def test_gate4_and_gate5_structural_checks():
    pricing = "## Tiers\n| Free | 0 |"
    policies = "Terms ... Privacy ... Refund ... not legal advice"
    assert evaluate_gate_4(pricing, policies).outcome == GateOutcome.GO
    assert evaluate_gate_4(pricing + " guaranteed income", policies).outcome == GateOutcome.STOP
    log = "IDEMPOTENCY: PASS\nREVOCATION: PASS\nRECONCILIATION: PASS"
    assert evaluate_gate_5(log, "PENDING_FOUNDER_APPROVAL").outcome == GateOutcome.GO
    assert evaluate_gate_5(log.replace("REVOCATION: PASS", "REVOCATION: FAIL")).outcome == GateOutcome.STOP
