"""Advisor memo: citation discipline, pain/coverage gap analysis, and that it never changes a gate."""
import json

import evidence
import gates
import insight_check
import orchestrator
from agents import advisor
from agents.builder import coverage
from models import Claim, FeatureSpec, FounderBrief, GateOutcome, GateResult, ResearchFindings, Source


def _strong_findings():
    snap = json.loads((orchestrator.SNAPSHOTS / "strong_scenario.json").read_text(encoding="utf-8"))
    srcs = [Source(**s) for s in snap["rounds"][0]["sources"]]
    brief = FounderBrief(idea=snap["rounds"][0]["idea"], target_user="university students", geography="Egypt",
                         language="Arabic/English")
    claims = evidence.verify_claims(evidence.extractive_claims(srcs, brief.idea, brief.target_user), srcs)
    return ResearchFindings(claims=claims, sources=srcs, evidence_mode="replay"), brief


def test_citation_check_removes_uncited_sentences():
    kept, removed = insight_check.check_lines(
        ["S2 says students struggle. Everyone wants this app.", "ASSUMPTION: price is unknown.", "S99 is invented."],
        {"S2"})
    assert kept == ["S2 says students struggle.", "ASSUMPTION: price is unknown."]
    assert removed == ["Everyone wants this app.", "S99 is invented."]


def test_pain_signal_and_coverage_gap_on_real_snapshot():
    f, brief = _strong_findings()
    pains = evidence.pain_signals(f.claims, brief.idea, brief.target_user)
    assert pains and pains[0]["key"] == "S6" and "preparation" in pains[0]["terms"]
    feats = [FeatureSpec(name="Due-today review queue", description="Shows only the cards due today.",
                         traces_to="x", action="due")]
    assert coverage(feats, pains)["covered"] == 0
    feats.append(FeatureSpec(name="Card preparation from notes", description="Turns notes into cards.",
                             traces_to="x", action="make"))
    assert coverage(feats, pains)["covered"] == 1


def test_memo_is_cited_advisory_and_leaves_the_gate_unchanged(monkeypatch):
    monkeypatch.setattr(advisor.callbacks, "log", lambda *a, **k: None)
    f, brief = _strong_findings()
    gate = gates.evaluate_gate_1(f, brief)
    before = (gate.outcome, gate.evidence_score, gates.compute_evidence_score(f))
    res = advisor.run("t-adv", 1, gate, brief, f)
    assert (gate.outcome, gate.evidence_score, gates.compute_evidence_score(f)) == before
    assert res["removed"] == []
    body = res["memo"].split("## 1.", 1)[1]
    for line in body.splitlines():
        if line.startswith("- ") and "nothing passed" not in line and line != "- none":
            assert insight_check.sentence_ok(line[2:].split(". ")[0] + ".", insight_check.verified_keys(f.claims)) \
                or "ASSUMPTION" in line, line
    assert "Removing" in res["memo"] or "No single source" in res["memo"]


def test_no_pain_means_no_invented_angle(monkeypatch):
    monkeypatch.setattr(advisor.callbacks, "log", lambda *a, **k: None)
    f = ResearchFindings(claims=[], sources=[], evidence_mode="replay")
    brief = FounderBrief(idea="generic study notes")
    g = GateResult(gate_id=1, outcome=GateOutcome.STOP, reason="x")
    memo = advisor.run("t-adv2", 1, g, brief, f)["memo"]
    assert "ASSUMPTION: no verified source describes demand" in memo
    assert "no angle is proposed rather than inventing one" in memo
