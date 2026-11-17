# MVP Specification — Founder brief:

I want to build an AI-powered flashcard and spaced-repetition study tool for university students in Egyp

> **STUBBED** — This specification was generated automatically. No code has been built or deployed.

## Problem

1. No quality Arabic-language spaced-repetition tool exists.
2. ASSUMPTION: Students waste time on ineffective revision methods.
3. ASSUMPTION: Existing tools lack STEM-specific content.

## User Stories

- As a ASSUMPTION: young adults aged 18–35 in the target geography, I want to access the core feature so I can solve my primary problem.
- As a ASSUMPTION: young adults aged 18–35 in the target geography, I want Arabic-language support so the tool works in my language.
- As a ASSUMPTION: young adults aged 18–35 in the target geography, I want a free tier so I can evaluate before paying.

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

ASSUMPTION: ~40 hours total (4 weeks × 10.0 h/week)

## Riskiest Assumptions to Validate Before Building

- Students will pay even a small monthly fee (risk: high)
- Arabic localisation is a sufficient differentiator (risk: medium)

## Feature → Problem Tracing

| Feature | Lean Canvas Problem |
|---|---|
| Core feature | 1. No quality Arabic-language spaced-repetition tool exists.... |
| Arabic UI | Local-constraints evidence |
| Free tier | Pricing/willingness-to-pay assumption |
