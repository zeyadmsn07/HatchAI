"""Strategist pivots, research-tool outage handling, evidence-specific critique, MVP pain response,
and the opt-in free-tier provider configuration. All offline."""
import json

import evidence
import gates
import llm_gateway
import orchestrator
from agents import builder, strategist, validator
from models import FounderBrief, GateOutcome, LeanCanvas, CanvasBlock, ResearchFindings, Source


def _strong():
    snap = json.loads((orchestrator.SNAPSHOTS / "strong_scenario.json").read_text(encoding="utf-8"))
    srcs = [Source(**s) for s in snap["rounds"][0]["sources"]]
    brief = FounderBrief(idea=snap["rounds"][0]["idea"], target_user="university students", geography="Egypt",
                         language="Arabic/English", skills="web development", hours_per_week=10)
    claims = evidence.verify_claims(evidence.extractive_claims(srcs, brief.idea, brief.target_user), srcs)
    return ResearchFindings(claims=claims, sources=srcs, evidence_mode="replay"), brief


def test_strategist_ranks_evidence_backed_candidates_with_source_keys():
    f, brief = _strong()
    cands = strategist.candidates(f, brief)
    assert cands, "the strong snapshot has a pain no competitor mentions"
    top = cands[0]
    assert top["kind"] == "pain_gap" and "S6" in top["keys"]
    assert "Narrow the idea" not in top["idea"] and top["idea"] != brief.idea
    assert all(c["score"] >= cands[i + 1]["score"] for i, c in enumerate(cands[:-1]))
    assert all(any(k in c["angle"] for k in c["keys"]) for c in cands)


def test_strategist_proposes_nothing_without_evidence():
    brief = FounderBrief(idea="A study app", target_user="students", geography="Egypt")
    assert strategist.candidates(ResearchFindings(), brief) == []


def _outage_findings(mode="live"):
    return ResearchFindings(evidence_mode=mode, tool_health={
        "jobs": 10, "ok": 1, "empty": 0, "failed": 9, "new_sources": 1,
        "errors": ["wikipedia: HTTPStatusError: 429 Too Many Requests"], "outage": True})


def test_tool_outage_is_repeat_not_weak_evidence():
    brief = FounderBrief(idea="A study app", target_user="students", geography="Egypt")
    g = gates.evaluate_gate_1(_outage_findings(), brief, round_no=1)
    assert g.outcome == GateOutcome.REPEAT and "research tools unavailable" in g.reason
    assert g.checks["research_tools_available"] is False
    g2 = gates.evaluate_gate_1(_outage_findings(), brief, round_no=2)
    assert g2.outcome == GateOutcome.STOP and "INCONCLUSIVE" in g2.reason and "not a verdict" in g2.reason


def test_tool_health_summary_flags_outage_only_when_calls_fail():
    bad = evidence.tool_health([("web", 0, ["web:x: ConnectError"])] * 6 + [("hn", 2, [])], 2)
    assert bad["outage"] and bad["failed"] == 6
    empty = evidence.tool_health([("web", 0, [])] * 6, 0)          # searches worked, found nothing
    assert not empty["outage"] and empty["failed"] == 0


def test_critique_risks_cite_the_evidence():
    f, brief = _strong()
    c = validator.run_critique("t-crit", brief, f)
    text = " ".join(r.assumption for r in c.riskiest_assumptions)
    assert "Target users will pay a recurring price" not in text
    assert any(k in text for k in ("S1", "S2", "S3", "S4", "S5", "S6"))
    assert all(r.kill_criterion for r in c.riskiest_assumptions)


def test_mvp_traces_are_not_circular_and_uncovered_pain_is_measured():
    f, brief = _strong()
    pains = evidence.pain_signals(f.claims, brief.idea, brief.target_user)
    blk = CanvasBlock(block="x", content="x")
    canvas = LeanCanvas(problem=blk, customer_segments=blk, unique_value_proposition=blk, solution=blk,
                        channels=blk, revenue_streams=blk, cost_structure=blk, key_metrics=blk,
                        unfair_advantage=blk)
    from models import Critique
    feats = builder._features("spaced_repetition", canvas, Critique(summary="", evidence_score=0,
                              viability_score=1, demand_signal="", founder_fit="",
                              recommendation=GateOutcome.GO), pains, "university students")
    assert not any("lack an adequate" in x.traces_to for x in feats)
    pq = [x for x in feats if x.name.startswith("Pain question")]
    assert pq and pq[0].action == "waitlist" and "S6" in pq[0].traces_to
    cov = builder.coverage(feats, pains)
    assert cov["covered"] == 0 and cov["rows"][0]["measured_by"]     # measured, never counted as solved
    assert builder.pain_question(pains, feats)


def test_hosted_provider_is_opt_in_open_weight_and_needs_a_key(monkeypatch):
    monkeypatch.delenv("HATCHAI_LLM_PROVIDER", raising=False)
    assert llm_gateway.provider() == "local"
    monkeypatch.setenv("HATCHAI_NO_LLM", "0")
    monkeypatch.setenv("HATCHAI_LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HATCHAI_LLM_API_KEY", raising=False)
    llm_gateway.reset_probe_cache()
    assert llm_gateway.base_urls() == ["https://api.groq.com/openai/v1"]
    assert llm_gateway.is_open_weight(llm_gateway.model_name())
    p = llm_gateway.probe(max_age=0)
    assert not p.reachable and "GROQ_API_KEY" in p.error
    monkeypatch.setenv("HATCHAI_LLM_HOSTED_MODEL", "gpt-4o")
    try:
        llm_gateway.model_name()
        assert False, "closed-weight model must be refused"
    except llm_gateway.ClosedWeightModelError:
        pass
    llm_gateway.reset_probe_cache()
