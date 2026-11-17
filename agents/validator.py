"""Validator agent — red-team critique, Lean Canvas, demand-test design.

Uses a different model family from the researcher for independent critique.
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from models import FounderBrief, ResearchFindings, Critique, LeanCanvas, DemandTest
import llm_gateway
import callbacks

SYSTEM_PROMPT = Path(__file__).parent.parent / "prompts" / "validator.md"


def run_critique(run_id: str, brief: FounderBrief, findings: ResearchFindings) -> Critique:
    system = SYSTEM_PROMPT.read_text(encoding="utf-8") if SYSTEM_PROMPT.exists() else _critique_system()
    user = (
        f"Idea: {brief.idea}\n"
        f"Geography: {brief.geography}\n"
        f"Budget USD: {brief.budget_usd}\n"
        f"Hours/week: {brief.hours_per_week}\n\n"
        f"Research claims:\n"
        + "\n".join(
            f"- [{c.category}] {c.text} (assumption={c.is_assumption})"
            for c in findings.claims
        )
    )
    result, model, tokens = llm_gateway.call_llm(system, user, Critique, temperature=0.4)

    callbacks.log(
        run_id=run_id,
        agent="validator",
        action="red_team_critique",
        sources=[],
        model=model,
        cost=0,
        phase=2,
        tokens=tokens,
    )
    return result


def run_canvas(run_id: str, brief: FounderBrief, findings: ResearchFindings,
               critique: Critique) -> LeanCanvas:
    user = (
        f"Idea: {brief.idea}\n"
        f"Target user: {brief.target_user}\n"
        f"Geography: {brief.geography}\n"
        f"Key risks: {[a.assumption for a in critique.riskiest_assumptions]}\n"
        f"Opportunity angles: {findings.opportunity_angles}"
    )
    system = (
        "You are a business model designer. Fill all 9 Lean Canvas blocks. "
        "Mark each block is_assumption=true unless you have verified evidence from the research. "
        "Return valid JSON matching LeanCanvas schema."
    )
    result, model, tokens = llm_gateway.call_llm(system, user, LeanCanvas, temperature=0.3)

    callbacks.log(
        run_id=run_id,
        agent="validator",
        action="build_lean_canvas",
        sources=[],
        model=model,
        cost=0,
        phase=2,
        tokens=tokens,
    )
    return result


def run_demand_test(run_id: str, brief: FounderBrief, canvas: LeanCanvas) -> DemandTest:
    user = (
        f"Idea: {brief.idea}\n"
        f"Budget USD: {brief.budget_usd}\n"
        f"Revenue stream: {canvas.revenue_streams.content}\n"
        f"Channels: {canvas.channels.content}"
    )
    system = (
        "Design a pre-registered demand test. "
        "Set status='NOT_RUN' — never simulate results. "
        "Keep cost within the stated budget. "
        "Return valid JSON matching DemandTest schema."
    )
    result, model, tokens = llm_gateway.call_llm(system, user, DemandTest, temperature=0.2)

    callbacks.log(
        run_id=run_id,
        agent="validator",
        action="design_demand_test",
        sources=[],
        model=model,
        cost=0,
        phase=2,
        tokens=tokens,
    )
    return result


def _critique_system() -> str:
    return (
        "You are a red-team validator using Mom-Test discipline. "
        "Separate verified evidence of past behaviour from opinions and hypotheticals. "
        "Rank the riskiest assumptions by impact × uncertainty. "
        "Rate viability_score 1–5; each rating must cite source keys or cap at 2. "
        "Set recommendation to go/repeat/pivot/stop based on the evidence. "
        "Return valid JSON matching Critique schema."
    )
