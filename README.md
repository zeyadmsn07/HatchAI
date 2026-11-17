# HatchAI — Evidence-Gated Open-Source Venture Builder

An open-source team of AI agents that takes a founder's idea through six evidence-gated phases toward a validated, sellable digital product. Every gate is a code-computed GO / REPEAT / PIVOT / STOP decision — no LLM can approve or publish anything.

## Quickstart

```bash
docker compose up
```

Then open **http://localhost:8000** in your browser.

Submit a founder brief in the form. The pipeline runs all six phases automatically in offline mock mode (no API keys needed). Click **Approve** or **Stop** at each gate decision.

To use real LLMs, copy `.env.example` to `.env` and add your free-tier API keys:
- `GEMINI_API_KEY` — Google AI Studio free tier (Gemini 1.5 Flash)
- `GROQ_API_KEY` — Groq free tier (Llama 3.3 70B)

## What works and what is mocked

| Phase / Component | Status | Notes |
|---|---|---|
| Intake & gap-finder | **Working** | Normalises brief, fills gaps with ASSUMPTION tags |
| Guardrail 0 (rule-based) | **Working** | Blocks excluded categories and trick intents, fail-closed |
| Evidence collector (web search) | **Working** | DuckDuckGo search; falls back to offline in mock mode |
| Researcher agent | **Working** | Synthesises claims with source keys; offline mode uses ASSUMPTION labels |
| Red-team validator + Lean Canvas | **Working** | Mom-Test critique, viability scoring, demand-test design |
| Evidence gates (Gate 1 & 2) | **Working** | E-score, V-score, hard-stop rules, GO/REPEAT/PIVOT/STOP |
| Founder approval at every gate | **Working** | Token-protected; override-stop requires written reason; logged |
| MVP spec generator | **STUBBED** | Markdown PRD + static HTML waitlist preview; no code built |
| Pricing & policy templates | **MOCKED** | ASSUMPTION-labelled pricing; policy templates marked "not legal advice" |
| Launch drafts | **MOCKED** | Drafts held as PENDING_FOUNDER_APPROVAL; never posted |
| Sale-to-Cash simulation | **MOCKED** | Local HMAC-signed events; idempotency, revocation, reconciliation |
| Operate & Learn memo | **MOCKED** | SYNTHETIC metrics (seed=42) vs pre-registered thresholds |
| Decision log | **Working** | Every agent action logged to `decision_log.json` and SQLite |
| Offline mode | **Working** | Full pipeline runs with no API keys; all outputs labelled |

## Architecture

HatchAI has two layers: a deterministic Python control plane (`orchestrator.py`, `gates.py`, `approval.py`) that owns all decisions and approvals, and an agent plane (`agents/`) that does language work via LiteLLM. Gate outcomes are computed from structured Pydantic-validated data — no LLM can advance a run, approve a gate, or trigger a payment. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

## Models and free resources

| Model | Provider | Used for |
|---|---|---|
| `gemini/gemini-1.5-flash` | Google AI Studio (free tier) | Intake, researcher, validator, builder |
| `groq/llama-3.3-70b-versatile` | Groq (free tier) | Fallback if Gemini unavailable |
| `offline-mock` | Local (no key needed) | Default when no API keys are set |

**To run completely free and locally:**
No API keys required. Set no environment variables — the app automatically uses `offline-mock` mode. All outputs are labelled ASSUMPTION / SYNTHETIC.

**To use real LLMs for free:**
1. Get a Google AI Studio key at [aistudio.google.com](https://aistudio.google.com) (free tier)
2. Add `GEMINI_API_KEY=your_key` to `.env`

## Cost per run

About **$0.00 per run** with offline mode (default, no API keys required).

With free-tier LLMs: **$0.00** (Gemini 1.5 Flash and Groq Llama 3.3 70B are both on free tiers).
Estimated token usage: ~15,000–40,000 tokens per full run.

## Demo video

*(Link to be added before final submission — recording a 3-minute walkthrough)*

## What our system will NOT do

- Promise income, profit, or success to any founder.
- Create fake reviews, testimonials, sign-ups, or countdown timers.
- Pose as a founder, customer, or any brand.
- Hold, move, or refund real money; create real accounts; store passwords or card numbers.
- Publish, send, or sign anything without an explicit founder approve/reject step in code.
- Build, deploy, or host any code on behalf of the founder.
- Advise on physical goods, financial/crypto/investment products, health, medical, or legal matters.
- Hide any core feature behind a paywall.

## How the project stays alive after the hackathon

**Maintainers:** The founding team will triage issues and merge community PRs on a best-effort basis.

**Roadmap:**
1. Plug in a real demand-test connector (self-hosted waitlist form → feeds Gate 2)
2. Regional evidence packs (Egypt/MENA country pack: local payment methods, statistics APIs)
3. Sandboxed MVP code scaffold (Phase 3 upgrade from spec to scaffolded repo)
4. Full Ollama local mode in `docker-compose.yml` (no internet required)
5. Public evaluation harness: benchmark briefs with expected gate outcomes, run in CI

**Community:** Issues and PRs welcome. The project is MIT-licensed and designed to be forked, extended, and localised.

**Funding:** No paid tier is planned. Infrastructure is minimal (SQLite + VPS). The project will seek community sponsorship if hosting costs grow.
