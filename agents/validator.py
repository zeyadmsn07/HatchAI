"""Validator agent — red-team critique, Lean Canvas, pre-registered demand test.

The viability score used by Gate 2 is computed in code (`gates.compute_viability`)
from verified evidence and founder fit. No LLM is used in this phase.
"""
from __future__ import annotations

import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import callbacks
import gates
from models import (CanvasBlock, Critique, DemandTest, FounderBrief, GateOutcome, KillAssumption,
                    LeanCanvas, ResearchFindings)


_GAP_RISKS = {
    "demand": ("Target users actively feel this problem today",
               "If fewer than 5 of 10 target-user interviews describe a recent, concrete instance of the problem, stop."),
    "competitors": ("No free incumbent already solves this well for this segment",
                    "If a free tool already covers the core job for this segment with good reviews, pivot."),
    "pricing": ("Target users will pay a recurring price",
                "If fewer than 3% of landing-page visitors click a priced plan, stop or pivot pricing."),
    "local_constraints": ("Users can access and pay for a digital product locally",
                          "If no local payment method is supported by an available sandbox processor, pivot channel."),
    "channels": ("We can reach target users at near-zero cost",
                 "If two community posts produce fewer than 100 landing-page visits, change channel."),
}


def _short(idea: str) -> str:
    """'An AI flashcard tool for students in Egypt, ...' -> 'AI flashcard tool'"""
    core = re.split(r"\s+(?:for|in|that|which|to help)\s+|[,.]", idea, maxsplit=1)[0]
    core = re.sub(r"(?i)^(an?|the)\s+", "", core.strip())
    return core[:100] or idea[:100]


def _verified(findings: ResearchFindings, cat: str):
    return [c for c in findings.claims if c.category == cat and c.verified]


def run_critique(run_id: str, brief: FounderBrief, findings: ResearchFindings) -> Critique:
    gaps = [cat for cat in _GAP_RISKS if not _verified(findings, cat)]
    risks = [KillAssumption(assumption=_GAP_RISKS["pricing"][0], risk="high",
                            kill_criterion=_GAP_RISKS["pricing"][1],
                            evidence_gaps=["No primary willingness-to-pay data (demand test NOT_RUN)"])]
    for cat in gaps:
        if cat == "pricing":
            continue
        risks.append(KillAssumption(assumption=_GAP_RISKS[cat][0],
                                    risk="high" if cat == "demand" else "medium",
                                    kill_criterion=_GAP_RISKS[cat][1],
                                    evidence_gaps=[f"No verified '{cat}' evidence in the source ledger"]))

    v, breakdown = gates.compute_viability(findings, brief, risks)
    summary = (f"{5 - len(gaps)}/5 evidence categories have verified, quoted sources "
               f"({', '.join(c for c in _GAP_RISKS if c not in gaps) or 'none'}). "
               f"Gaps: {', '.join(gaps) or 'none'}. Willingness to pay is untested until the "
               f"pre-registered demand test runs.")
    model, tokens = None, 0

    critique = Critique(
        summary=summary,
        riskiest_assumptions=risks,
        evidence_score=findings.evidence_score,
        viability_score=v,
        viability_breakdown=breakdown,
        demand_signal=_signal(findings, "demand"),
        founder_fit=(f"Skills: {brief.skills}; {brief.hours_per_week} h/week; budget USD {brief.budget_usd}. "
                     f"Founder-fit points: {breakdown.get('founder_skills', 0) + breakdown.get('founder_time', 0)}"),
        recommendation=GateOutcome.GO,  # placeholder: Gate 2 (code) sets the real outcome
        unresolved_kill_assumptions=sum(1 for a in risks if a.risk == "high" and not a.kill_criterion),
    )
    callbacks.log(run_id=run_id, agent="validator", action="red_team_critique",
                  sources=_urls(findings, None), model=model, cost=0, phase=2, tokens=tokens)
    return critique


def _signal(findings: ResearchFindings, cat: str) -> str:
    v = _verified(findings, cat)
    if not v:
        return f"ASSUMPTION: no verified {cat} evidence."
    return " | ".join(f"{c.text[:200]} [{', '.join(c.source_keys)}]" for c in v)


def _urls(findings: ResearchFindings, cat: str | None) -> list[str]:
    keys = {k for c in findings.claims if c.verified and (cat is None or c.category == cat) for k in c.source_keys}
    return [s.url for s in findings.sources if s.key in keys]


def run_canvas(run_id: str, brief: FounderBrief, findings: ResearchFindings, critique: Critique) -> LeanCanvas:
    def block(name, content, cat=None):
        claims = _verified(findings, cat) if cat else []
        keys = sorted({k for c in claims for k in c.source_keys})
        if claims:
            content = f"{content} Evidence: {claims[0].text[:160]}"
        return CanvasBlock(block=name, content=content, source_keys=keys, is_assumption=not keys)

    top_risk = critique.riskiest_assumptions[0].assumption if critique.riskiest_assumptions else ""
    canvas = LeanCanvas(
        problem=block("Problem", f"{brief.target_user} lack an adequate {_short(brief.idea)}.", "demand"),
        customer_segments=block("Customer Segments", f"{brief.target_user} in {brief.geography}."),
        unique_value_proposition=block("Unique Value Proposition",
                                       f"A focused {brief.language} tool for {brief.target_user}, not a generic suite.",
                                       "competitors"),
        solution=block("Solution", f"Smallest working version of: {brief.idea[:140]} (see Phase 3 MVP)."),
        channels=block("Channels", "Communities where the target user already gathers.", "channels"),
        revenue_streams=block("Revenue Streams", "Free core tier + paid tier (prices in Phase 4).", "pricing"),
        cost_structure=block("Cost Structure",
                             f"Founder time ({brief.hours_per_week} h/week), hosting, open-weight models at USD 0."),
        key_metrics=block("Key Metrics", f"Demand-test sign-up rate; weekly active users; riskiest: {top_risk}."),
        unfair_advantage=block("Unfair Advantage", f"Founder skills: {brief.skills}; local context: {brief.geography}.",
                               "local_constraints"),
    )
    callbacks.log(run_id=run_id, agent="validator", action="build_lean_canvas",
                  sources=_urls(findings, None), model=None, cost=0, phase=2)
    return canvas


def run_demand_test(run_id: str, brief: FounderBrief, canvas: LeanCanvas) -> DemandTest:
    cost = round(min(max(brief.budget_usd, 0) * 0.1, 50.0), 2)
    min_visitors, go_rate, stop_rate = 300, 0.10, 0.03
    dt = DemandTest(
        channel=("Free posts in 2 communities where the target user gathers + the Phase 3 MVP landing page"
                 if cost == 0 else
                 f"Community posts + up to USD {cost} of targeted ads to the Phase 3 MVP landing page"),
        metric="Unique visitors who submit an email on the waitlist form (double opt-in)",
        threshold=(f"GO if >= {go_rate:.0%} of >= {min_visitors} unique visitors sign up within 14 days; "
                   f"STOP if < {stop_rate:.0%}"),
        duration_days=14,
        cost_usd=cost,
        status="NOT_RUN",
        min_unique_visitors=min_visitors,
        go_signup_rate=go_rate,
        stop_signup_rate=stop_rate,
    )
    callbacks.log(run_id=run_id, agent="validator", action="design_demand_test", sources=[],
                  model=None, cost=0, phase=2)
    return dt
