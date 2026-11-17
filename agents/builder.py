"""Builder agent — STUBBED.

Produces a Markdown PRD and a static HTML waitlist preview.
No code is generated, deployed, or hosted.
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import FounderBrief, LeanCanvas, Critique
import callbacks


def run(run_id: str, brief: FounderBrief, canvas: LeanCanvas, critique: Critique) -> dict:
    """Return {'mvp_spec': str, 'waitlist_html': str}."""
    mvp_spec = _build_spec(brief, canvas, critique)
    waitlist_html = _build_waitlist(brief)

    callbacks.log(
        run_id=run_id,
        agent="builder",
        action="generate_mvp_spec",
        sources=[],
        model="offline-mock",
        cost=0,
        phase=3,
    )
    return {"mvp_spec": mvp_spec, "waitlist_html": waitlist_html}


def _build_spec(brief: FounderBrief, canvas: LeanCanvas, critique: Critique) -> str:
    risks = "\n".join(f"- {a.assumption} (risk: {a.risk})" for a in critique.riskiest_assumptions)
    return f"""# MVP Specification — {brief.idea}

> **STUBBED** — This specification was generated automatically. No code has been built or deployed.

## Problem

{canvas.problem.content}

## User Stories

- As a {brief.target_user}, I want to access the core feature so I can solve my primary problem.
- As a {brief.target_user}, I want Arabic-language support so the tool works in my language.
- As a {brief.target_user}, I want a free tier so I can evaluate before paying.

## Scope

**In scope (MVP):**
- Core value proposition feature only
- User authentication (email + password, no OAuth for MVP)
- Basic Arabic/English UI
- Free tier + paid subscription upgrade flow (MOCKED — no real payments)

**Out of Scope (MVP)**
- Mobile native app (web-first only)
- Advanced analytics
- API access
- Team / multi-seat plans

## Stack

- **Backend:** Python / FastAPI
- **Frontend:** HTML + HTMX (no JS framework)
- **Database:** SQLite (dev), PostgreSQL (production)
- **Hosting:** Any VPS / Render / Railway (ASSUMPTION)
- **Payments:** Stripe checkout (MOCKED — not implemented)

## Effort Estimate

ASSUMPTION: ~{int(brief.hours_per_week * 4)} hours total (4 weeks × {brief.hours_per_week} h/week)

## Riskiest Assumptions to Validate Before Building

{risks}

## Feature → Problem Tracing

| Feature | Lean Canvas Problem |
|---|---|
| Core feature | {canvas.problem.content[:60]}... |
| Arabic UI | Local-constraints evidence |
| Free tier | Pricing/willingness-to-pay assumption |
"""


def _build_waitlist(brief: FounderBrief) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{brief.idea} — Coming Soon</title>
<style>
  body {{ font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 20px; }}
  .badge {{ background: #f59e0b; color: #000; padding: 4px 10px; border-radius: 4px;
            font-weight: bold; font-size: 0.8em; }}
  input {{ width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; }}
  button {{ background: #ccc; color: #666; padding: 10px 20px; cursor: not-allowed; }}
</style>
</head>
<body>
<p><span class="badge">MOCKED — form not connected</span></p>
<h1>{brief.idea}</h1>
<p>We're building something for <strong>{brief.target_user}</strong> in <strong>{brief.geography}</strong>.</p>
<p>Join the waitlist to be first to know when we launch.</p>
<form onsubmit="return false;">
  <input type="email" placeholder="your@email.com" disabled>
  <button type="submit" disabled>Join Waitlist (not active)</button>
</form>
<p><small>No real data is collected. This is a static preview only.</small></p>
</body>
</html>"""
