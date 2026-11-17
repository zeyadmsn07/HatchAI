"""Research agent — evidence collection, synthesis, citation verification.

1. `evidence.collect` (no LLM) queries web search, Hacker News, Wikipedia and the
   World Bank API, and stores every passage in a source ledger.
2. Synthesis (no LLM — claims feed the evidence score, so they must be code-derived):
   extractive mode — claims are verbatim passages from fetched sources. Snapshots captured
   by older versions with LLM-written claims still replay those stored claims.
3. `evidence.verify_claims` re-checks every quote against the fetched text.
   Failed citations are downgraded to ASSUMPTION. Categories with no verified
   claim get an explicit ASSUMPTION placeholder so gaps are visible.
4. The Strategist (`agents/strategist.py`) ranks evidence-backed pivot candidates; the best one
   becomes the pivot the gate proposes. Replays of snapshots captured before the Strategist
   existed (no `angles_version` 2) keep the legacy angles, because their pivot round was collected
   for that text.
5. In a LIVE run the research tools' health is recorded, so a rate-limited or offline search
   is reported as "tools unavailable" rather than scored as weak evidence.
"""
from __future__ import annotations

import logging
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import callbacks
import evidence
from agents import strategist
from models import Claim, FounderBrief, ResearchFindings

ANGLES_VERSION = 2

log = logging.getLogger(__name__)



def _clean(v: str) -> str:
    return "" if v.upper().startswith(("UNKNOWN", "ASSUMPTION")) else v


def run(run_id: str, brief: FounderBrief, round_no: int = 1,
        previous: ResearchFindings | None = None, idea_override: str | None = None,
        replay: dict | None = None, capture: list | None = None, scoring: str = "v1") -> ResearchFindings:
    """Research one round.

    replay:  a captured evidence snapshot; sources (and captured raw LLM claims, if any) are
             loaded from it instead of being collected — no network and no LLM call.
    capture: a list that receives this round's record (sources, raw claims, verified claims)
             so the run can be saved as a snapshot.
    """
    idea = idea_override or brief.idea
    target, geo = _clean(brief.target_user), _clean(brief.geography)

    existing = previous.sources if previous else []
    claims: list[Claim] = []
    angles: list[str] = []
    model, tokens, mode = None, 0, "extractive"
    health: dict = {}
    angles_version = ANGLES_VERSION
    if replay is not None:
        sources, rnd = evidence.replay_collect(replay, idea, round_no, existing)
        new_sources = sources[len(existing):]
        claims = [Claim(**c) for c in rnd.get("raw_claims", [])]
        angles = list(rnd.get("raw_angles", []))
        mode = rnd.get("synthesis_mode", "extractive")
        angles_version = int(rnd.get("angles_version", 1))
        callbacks.log(run_id=run_id, agent="researcher", action=f"replay_evidence_round_{round_no}",
                      sources=[s.url for s in new_sources], model=None, cost=0, phase=1,
                      outcome=f"REPLAY of snapshot {replay.get('_file', '?')} captured {replay.get('captured_at', '?')}; "
                              "no new collection")
    else:
        sources, _ = evidence.collect(idea, target, geo, round_no=round_no, existing=existing, health=health)
        new_sources = sources[len(existing):]
        callbacks.log(run_id=run_id, agent="researcher", action=f"collect_evidence_round_{round_no}",
                      sources=[s.url for s in new_sources], model=None, cost=0, phase=1,
                      outcome="LIVE collection in this run" + (
                          f"; tools: {health.get('ok', 0)}/{health.get('jobs', 0)} returned results, "
                          f"{health.get('failed', 0)} failed" if health else "")
                              + ("; RESEARCH TOOLS UNAVAILABLE" if health.get("outage") else ""))

    raw_claims = [c.model_copy() for c in claims]
    raw_angles = list(angles)

    claims = evidence.verify_claims(claims, sources)
    verified_cats = {c.category for c in claims if c.verified}
    # Fill categories the model missed (or all of them in no-LLM mode) with verbatim extracts.
    for c in evidence.extractive_claims(sources, idea, target, scoring, brief.geography, brief.language):
        if c.category not in verified_cats:
            claims.append(c)
    claims = evidence.verify_claims(claims, sources)
    verified_cats = {c.category for c in claims if c.verified}
    for cat in evidence.CATEGORIES:
        if cat not in verified_cats:
            claims.append(Claim(category=cat, text=f"ASSUMPTION: no verified evidence found for '{cat}'.",
                                verified=False, is_assumption=True))

    findings = ResearchFindings(
        claims=claims, opportunity_angles=angles, sources=sources, tool_health=health,
        source_count=len(sources), domain_count=len({s.domain for s in sources}),
        research_round=round_no, mode=mode, scoring_version=scoring,
        evidence_mode="replay" if replay is not None else "live",
        snapshot=(f"{replay.get('_file', '?')} (captured {replay.get('captured_at', '?')})" if replay is not None else ""),
    )
    cands = strategist.candidates(findings, brief.model_copy(update={"idea": idea}))
    findings.evidence_angles = [c["angle"] for c in cands]
    if not findings.opportunity_angles:
        legacy = strategist.legacy_angles(brief, idea, verified_cats)
        if angles_version >= 2:
            fresh = [c["idea"] for c in cands if c["idea"].strip().lower() != idea.strip().lower()]
            findings.opportunity_angles = fresh + legacy[:1]
        else:
            findings.opportunity_angles = legacy
    if capture is not None:
        capture.append({
            "round": round_no, "idea": idea, "target_user": target, "geography": geo,
            "synthesis_mode": mode, "model": model, "angles_version": ANGLES_VERSION,
            "tool_health": health,
            "queries": evidence.plan_queries(idea, target, geo, round_no),
            "sources": [s.model_dump() for s in new_sources],
            "raw_claims": [c.model_dump() for c in raw_claims],
            "raw_angles": raw_angles,
            "verified_claims_at_capture": [c.model_dump() for c in claims if c.verified],
            "evidence_score_at_capture": None,   # filled in by the orchestrator after the gate
        })
    callbacks.log(run_id=run_id, agent="researcher", action="synthesize_and_verify_claims",
                  sources=sorted({s.url for c in claims if c.verified
                                  for s in sources if s.key in c.source_keys}),
                  model=model, cost=0, phase=1, tokens=tokens)
    return findings
