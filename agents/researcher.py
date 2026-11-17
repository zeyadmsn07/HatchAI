"""Research agent — web search + evidence synthesis.

Evidence collector: ddgs (DuckDuckGo) → extract with trafilatura → passage ranking.
Researcher LLM: synthesises claims with source keys only (never sees URLs).
In offline mode: returns pre-built ASSUMPTION-labelled findings.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from datetime import datetime, timezone

from models import FounderBrief, ResearchFindings, Source
import llm_gateway
import callbacks

log = logging.getLogger(__name__)

SYSTEM_PROMPT = Path(__file__).parent.parent / "prompts" / "researcher.md"


def run(run_id: str, brief: FounderBrief) -> ResearchFindings:
    sources = _collect_evidence(run_id, brief)

    if not sources:
        log.info("No sources fetched — using offline research findings")
        findings, model, tokens = llm_gateway.call_llm(
            _system(), _user_prompt(brief, []), ResearchFindings, temperature=0.3
        )
        findings.sources = llm_gateway._offline_sources()
        findings.source_count = len(findings.sources)
        findings.domain_count = len({s.domain for s in findings.sources})
    else:
        passages_ctx = _build_passage_context(sources)
        findings, model, tokens = llm_gateway.call_llm(
            _system(), _user_prompt(brief, passages_ctx), ResearchFindings, temperature=0.3
        )
        findings.sources = sources

    callbacks.log(
        run_id=run_id,
        agent="researcher",
        action="synthesize_findings",
        sources=[s.url for s in findings.sources],
        model=model,
        cost=0,
        phase=1,
        tokens=tokens,
    )
    return findings


def _collect_evidence(run_id: str, brief: FounderBrief) -> list[Source]:
    queries = _build_queries(brief)
    sources: list[Source] = []

    try:
        from ddgs import DDGS  # type: ignore
        with DDGS() as ddgs:
            for q in queries[:4]:
                try:
                    results = list(ddgs.text(q, max_results=3))
                    for r in results:
                        url = r.get("href", "")
                        title = r.get("title", "")
                        body = r.get("body", "")
                        if not url:
                            continue
                        domain = _domain(url)
                        if any(s.domain == domain for s in sources):
                            continue
                        sources.append(Source(
                            key=f"S{len(sources)+1}",
                            url=url,
                            title=title,
                            domain=domain,
                            fetch_time=datetime.now(timezone.utc).isoformat(),
                            text_hash=hashlib.sha256(body.encode()).hexdigest()[:16],
                            passages=[body[:300]] if body else [],
                        ))
                        if len(sources) >= 5:
                            break
                except Exception as exc:
                    log.warning("DDGS query failed: %s", exc)
    except ImportError:
        log.warning("duckduckgo-search not available; using offline sources")
    except Exception as exc:
        log.warning("Evidence collection failed: %s; using offline sources", exc)

    callbacks.log(
        run_id=run_id,
        agent="researcher",
        action="collect_evidence",
        sources=[s.url for s in sources],
        model=None,
        cost=0,
        phase=1,
    )
    return sources


def _build_queries(brief: FounderBrief) -> list[str]:
    idea = brief.idea[:80]
    geo = brief.geography.replace("ASSUMPTION: ", "")
    return [
        f"{idea} market size demand {geo}",
        f"{idea} competitors alternatives",
        f"{idea} pricing willingness to pay {geo}",
        f"digital products {geo} online market",
        f"{geo} internet users students digital tools",
    ]


def _build_passage_context(sources: list[Source]) -> list[str]:
    ctx = []
    for s in sources:
        for p in s.passages[:2]:
            ctx.append(f"[{s.key}] {p[:200]}")
    return ctx


def _system() -> str:
    path = SYSTEM_PROMPT
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "You are a research analyst. Given search result passages labelled S1..Sn, "
        "synthesise findings. Write claims as {category, text, source_keys, quote}. "
        "Mark any claim not backed by a source passage as is_assumption=true. "
        "Return valid JSON matching ResearchFindings schema."
    )


def _user_prompt(brief: FounderBrief, passages: list[str]) -> str:
    ps = "\n".join(passages) if passages else "(no passages — offline mode, all claims are ASSUMPTION)"
    return f"Idea: {brief.idea}\nGeography: {brief.geography}\n\nPassages:\n{ps}"


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return url[:30]
