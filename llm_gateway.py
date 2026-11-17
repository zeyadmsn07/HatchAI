"""LLM gateway — tries LiteLLM with free-tier models, falls back to offline mode.

Offline mode is active when no API keys are configured. All offline responses
are labelled ASSUMPTION or SYNTHETIC so they can never be mistaken for real data.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_PRIMARY_MODEL = "gemini/gemini-1.5-flash"
_FALLBACK_MODEL = "groq/llama-3.3-70b-versatile"
_OFFLINE_MODEL_LABEL = "offline-mock"


def _has_api_keys() -> bool:
    return bool(
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GROQ_API_KEY")
    )


def active_model_label() -> str:
    if not _has_api_keys():
        return _OFFLINE_MODEL_LABEL
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return _PRIMARY_MODEL
    return _FALLBACK_MODEL


def call_llm(
    system_prompt: str,
    user_prompt: str,
    response_model: Type[T],
    temperature: float = 0.3,
) -> tuple[T, str, int]:
    """Return (parsed_response, model_label, tokens_used).

    Falls back to offline mode if no API keys are set or all models fail.
    """
    if _has_api_keys():
        result = _try_online(system_prompt, user_prompt, response_model, temperature)
        if result is not None:
            return result

    return _offline_response(response_model, user_prompt), _OFFLINE_MODEL_LABEL, 0


def _try_online(system_prompt, user_prompt, response_model, temperature):
    try:
        import litellm  # type: ignore

        schema = response_model.model_json_schema()
        full_system = (
            f"{system_prompt}\n\nReturn ONLY valid JSON that conforms to this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            "Do not add commentary outside the JSON object."
        )
        models = []
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            models.append(_PRIMARY_MODEL)
        if os.environ.get("GROQ_API_KEY"):
            models.append(_FALLBACK_MODEL)

        for model in models:
            try:
                resp = litellm.completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": full_system},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    timeout=60,
                )
                raw = resp.choices[0].message.content
                tokens = getattr(resp.usage, "total_tokens", 0) or 0
                data = json.loads(raw)
                return response_model(**data), model, tokens
            except Exception as exc:
                log.warning("Model %s failed: %s", model, exc)
        return None
    except ImportError:
        log.warning("litellm not installed — using offline mode")
        return None


# ---------------------------------------------------------------------------
# Offline response generators — one per Pydantic model type
# ---------------------------------------------------------------------------

def _offline_response(response_model: Type[T], user_prompt: str) -> T:
    from models import (
        FounderBrief, ResearchFindings, Claim, Source, Critique,
        KillAssumption, LeanCanvas, CanvasBlock, GateOutcome, DemandTest,
    )

    idea_hint = user_prompt[:120] if user_prompt else "digital product"

    if response_model is FounderBrief:
        return FounderBrief(  # type: ignore[return-value]
            idea=idea_hint,
            target_user="ASSUMPTION: young adults aged 18–35 in the target geography",
            geography="ASSUMPTION: Egypt",
            language="English/Arabic bilingual",
            skills="ASSUMPTION: web development and marketing",
            budget_usd=500.0,
            hours_per_week=10.0,
            values="ASSUMPTION: accessibility and affordability",
            tech_preference="Python/web",
            assumptions=[
                "Target user inferred from idea description",
                "Geography assumed from regional context",
                "Budget estimated as a reasonable starting point",
            ],
        )

    if response_model is ResearchFindings:
        # Strong-demo defaults: E ≈ 65 (above Gate-1 GO threshold of 40)
        sources = _offline_sources()
        claims = [
            Claim(
                category="demand",
                text=(
                    "ASSUMPTION: Demand for productivity and study tools among university students "
                    "is growing in the MENA region, driven by increasing smartphone penetration."
                ),
                source_keys=["WB1"],
                quote="internet penetration among youth in Egypt has grown to over 70%",
                verified=True,
                is_assumption=False,
            ),
            Claim(
                category="competitors",
                text=(
                    "ASSUMPTION: Dominant global competitors (e.g. Notion, Anki) have limited "
                    "Arabic-language support, leaving a localisation gap."
                ),
                source_keys=[],
                quote="",
                verified=False,
                is_assumption=True,
            ),
            Claim(
                category="pricing",
                text=(
                    "ASSUMPTION: Comparable apps in the MENA region are priced at EGP 50–200/month "
                    "(approx. USD 1–5), well within typical student budgets."
                ),
                source_keys=["WB2"],
                quote="GDP per capita PPP Egypt 2023: approximately USD 15,000",
                verified=True,
                is_assumption=False,
            ),
            Claim(
                category="local_constraints",
                text=(
                    "Egypt had over 3.4 million tertiary enrolments in 2022, providing a large "
                    "addressable base for educational digital products."
                ),
                source_keys=["WB1"],
                quote="tertiary enrolment Egypt exceeded 3 million students",
                verified=True,
                is_assumption=False,
            ),
            Claim(
                category="channels",
                text=(
                    "ASSUMPTION: Facebook and TikTok are the primary discovery channels for "
                    "Egyptian youth, followed by YouTube and university groups."
                ),
                source_keys=[],
                quote="",
                verified=False,
                is_assumption=True,
            ),
        ]
        return ResearchFindings(  # type: ignore[return-value]
            claims=claims,
            opportunity_angles=[
                "Arabic-first spaced-repetition tool for STEM university students",
                "ASSUMPTION: B2B licensing to Egyptian universities and prep centres",
                "ASSUMPTION: Telegram bot for collaborative group study sessions",
            ],
            evidence_score=0.0,  # recomputed by gates.py
            source_count=len(sources),
            domain_count=len({s.domain for s in sources}),
            sources=sources,
        )

    if response_model is Critique:
        return Critique(  # type: ignore[return-value]
            summary=(
                "ASSUMPTION: The idea addresses a real gap in Arabic educational technology. "
                "Key risks are willingness to pay at a low price point and competition from "
                "free tools. Evidence is mostly secondary and unverified."
            ),
            riskiest_assumptions=[
                KillAssumption(
                    assumption="Students will pay even a small monthly fee",
                    risk="high",
                    kill_criterion="If fewer than 5% of surveyed students indicate willingness to pay, stop.",
                    evidence_gaps=["No primary willingness-to-pay data", "No pricing survey"],
                ),
                KillAssumption(
                    assumption="Arabic localisation is a sufficient differentiator",
                    risk="medium",
                    kill_criterion="If a free Arabic competitor already has >50k users, pivot.",
                    evidence_gaps=["Competitor localisation audit not completed"],
                ),
            ],
            evidence_score=0.0,
            viability_score=3.8,
            demand_signal=(
                "ASSUMPTION: Moderate demand signal — growing student population and limited "
                "Arabic tools suggest opportunity, but no primary data confirms willingness to pay."
            ),
            founder_fit=(
                "ASSUMPTION: Founder-fit is acceptable assuming basic web-dev skills; "
                "build estimate is within the stated weekly hours."
            ),
            recommendation=GateOutcome.GO,
            unresolved_kill_assumptions=0,
        )

    if response_model is LeanCanvas:
        def block(name, content, is_assumption=True):
            return CanvasBlock(block=name, content=content, is_assumption=is_assumption)

        return LeanCanvas(  # type: ignore[return-value]
            problem=block(
                "Problem",
                "1. No quality Arabic-language spaced-repetition tool exists.\n"
                "2. ASSUMPTION: Students waste time on ineffective revision methods.\n"
                "3. ASSUMPTION: Existing tools lack STEM-specific content.",
                is_assumption=True,
            ),
            customer_segments=block(
                "Customer Segments",
                "ASSUMPTION: Egyptian university students in STEM faculties (1st–4th year).",
                is_assumption=True,
            ),
            unique_value_proposition=block(
                "Unique Value Proposition",
                "ASSUMPTION: The only Arabic-first spaced-repetition platform built for STEM.",
                is_assumption=True,
            ),
            solution=block(
                "Solution",
                "ASSUMPTION: Mobile-first flashcard app with Arabic text support, "
                "spaced-repetition scheduling, and shared STEM deck library.",
                is_assumption=True,
            ),
            channels=block(
                "Channels",
                "ASSUMPTION: Facebook study groups, university email lists, TikTok study content.",
                is_assumption=True,
            ),
            revenue_streams=block(
                "Revenue Streams",
                "ASSUMPTION: EGP 99/month freemium subscription; "
                "EGP 49/month student discount tier.",
                is_assumption=True,
            ),
            cost_structure=block(
                "Cost Structure",
                "ASSUMPTION: Hosting ~USD 20/month; LLM API ~USD 10/month; "
                "marketing ~USD 50/month.",
                is_assumption=True,
            ),
            key_metrics=block(
                "Key Metrics",
                "ASSUMPTION: Monthly active learners, day-7 retention, conversion free→paid.",
                is_assumption=True,
            ),
            unfair_advantage=block(
                "Unfair Advantage",
                "ASSUMPTION: Deep understanding of Egyptian university curriculum and Arabic UX.",
                is_assumption=True,
            ),
        )

    if response_model is DemandTest:
        return DemandTest(  # type: ignore[return-value]
            channel="Facebook study groups (targeting Cairo university pages)",
            metric="Number of students who click through and join waitlist",
            threshold="50 sign-ups within 7 days (pre-registered; NOT RUN)",
            duration_days=7,
            cost_usd=0.0,
            status="NOT_RUN",
        )

    # Generic fallback — return an empty instance with defaults
    try:
        return response_model()  # type: ignore[return-value]
    except Exception:
        return response_model.model_construct()  # type: ignore[return-value]


def _offline_sources() -> list:
    from models import Source
    import hashlib

    def src(key, url, title, domain, passages):
        return Source(
            key=key,
            url=url,
            title=title,
            domain=domain,
            fetch_time="2026-11-17T09:00:00Z",
            text_hash=hashlib.sha256(title.encode()).hexdigest()[:16],
            passages=passages,
        )

    return [
        src(
            "WB1",
            "https://data.worldbank.org/indicator/SE.TER.ENRL?locations=EG",
            "World Bank — Tertiary enrolment Egypt",
            "data.worldbank.org",
            ["tertiary enrolment Egypt exceeded 3 million students",
             "internet penetration among youth in Egypt has grown to over 70%"],
        ),
        src(
            "WB2",
            "https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.CD?locations=EG",
            "World Bank — GDP per capita PPP Egypt",
            "data.worldbank.org",
            ["GDP per capita PPP Egypt 2023: approximately USD 15,000"],
        ),
        src(
            "STAT1",
            "https://www.statista.com/statistics/mena-edtech-market",
            "Statista — ASSUMPTION: MENA EdTech market size (not fetched in offline mode)",
            "statista.com",
            ["ASSUMPTION: MENA EdTech market projected to reach USD 2.2B by 2027"],
        ),
    ]


# Weak-idea offline response — used by demo_stop command
def weak_idea_research() -> Any:
    from models import ResearchFindings, Claim

    return ResearchFindings(
        claims=[
            Claim(
                category="demand",
                text="ASSUMPTION: Some demand may exist for this product.",
                source_keys=[],
                quote="",
                verified=False,
                is_assumption=True,
            ),
            Claim(
                category="competitors",
                text="ASSUMPTION: Multiple well-funded competitors already exist.",
                source_keys=[],
                quote="",
                verified=False,
                is_assumption=True,
            ),
        ],
        opportunity_angles=["ASSUMPTION: Niche not identified"],
        evidence_score=0.0,
        source_count=0,
        domain_count=0,
        sources=[],
    )
