"""Intake agent — normalises the founder brief and fills gaps with ASSUMPTION tags."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from models import FounderBrief
import llm_gateway
import callbacks


SYSTEM_PROMPT = Path(__file__).parent.parent / "prompts" / "intake.md"


def run(run_id: str, raw_text: str) -> FounderBrief:
    system = SYSTEM_PROMPT.read_text(encoding="utf-8") if SYSTEM_PROMPT.exists() else _default_system()
    user = f"Founder brief:\n\n{raw_text}"

    result, model, tokens = llm_gateway.call_llm(system, user, FounderBrief, temperature=0.2)

    callbacks.log(
        run_id=run_id,
        agent="intake",
        action="normalize_brief",
        sources=[],
        model=model,
        cost=0,
        phase=1,
        tokens=tokens,
    )
    return result


def _default_system() -> str:
    return (
        "You are an intake agent for a venture builder. "
        "Given a founder's raw idea description, normalise it into structured fields. "
        "Fill any missing field with 'ASSUMPTION: <your best guess>'. "
        "Return valid JSON matching the FounderBrief schema."
    )
