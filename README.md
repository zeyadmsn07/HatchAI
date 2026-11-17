# HatchAI: evidence-gated open-source venture builder

An open-source team of agents that takes a founder's idea through six gated phases (Discover → Validate → Build → Commercial → Sell/deliver/get paid → Operate). It **generates and tests a runnable, idea-specific MVP**, and recommends **STOP** when the evidence is weak.

- **Evidence by construction:** live, keyless sources (web search, Hacker News, Wikipedia, World Bank). Every quote is re-checked against the fetched text by code; anything unverified is labelled `ASSUMPTION`.
- **Code decides, LLMs propose:** evidence and viability scores and GO / REPEAT / PIVOT / STOP are computed in Python. Nothing proceeds without a founder decision enforced in `approval.py`.
- **Phase 3 builds real software:** 5 tested archetypes (SM-2 flashcards, booking, habit tracker, directory, course). The generated app gets its own idea-specific tests, which the pipeline runs before Gate 3 can pass.
- **Open-weight only:** Ollama (`qwen3:8b` by default) or Llama 3.3 70B on Groq's free tier. Closed-weight model names are refused in code. With no model, every agent has a labelled rule-based path. Cost: $0.

**Committed demo run** (`python orchestrator.py demo`, outputs in [`outputs/`](outputs/), log in [`decision_log.json`](decision_log.json)):
the strong brief (STEM flashcards, Egypt) gets G1–G5 **GO**. Its MVP *STEM Recall* passed **21/21** generated tests and booted. The weak brief ("generic study notes", no user, no country) is stopped at **Gate 1: STOP**.

## Quickstart

```bash
docker compose up
```

Open **http://localhost:8000**, submit a brief, and decide each gate (Approve / Repeat / Pivot / Stop, or override with a written reason). Output files and the path of the generated MVP appear on the run page.

Optional extras:

```bash
docker compose --profile llm up          # also starts Ollama and pulls qwen3:8b (~5 GB, once)
python orchestrator.py demo               # regenerate outputs/ + decision_log.json (no Docker)
python orchestrator.py run "<brief>"      # CLI run; you approve every gate at the prompt
cd generated_mvps/demo-strong && python server.py --port 8080   # run the generated MVP
python -m pytest                          # 59 tests: gates, approval, evidence, builder, pipeline, web
```

Without Docker: `pip install -r requirements.txt && uvicorn app:app` (Python 3.12).

## What works and what is mocked

| Step | Status | Notes |
|---|---|---|
| 1.1 Intake | **Working** | Deterministic parser; unstated fields → `UNKNOWN`/`ASSUMPTION` (LLM can only rephrase) |
| 1.2 Guardrail 0 | **Working** | Excluded products and trick intents, fail-closed, no override; re-run on pivots |
| 1.3 Evidence collection | **Working** | `ddgs` web, HN Algolia, Wikipedia, World Bank API; ledger with URL + SHA-256 |
| 1.4 Synthesis + citation verifier | **Working** | LLM or extractive (no-LLM) mode; quotes re-matched to fetched text |
| Gate 1 | **Working** | E-score; GO / REPEAT (2nd research round) / PIVOT / STOP |
| 2.1 Red-team critique + viability | **Working** | V-score computed in code; LLM critique optional |
| 2.2 Lean Canvas | **Working** | Blocks cite source keys or say `ASSUMPTION` |
| 2.3 Demand test | **Working** design / **STUBBED** execution | Pre-registered thresholds; `NOT_RUN` until the founder runs it |
| Gate 2 | **Working** | GO / REPEAT / PIVOT / STOP |
| 3.1 MVP spec + template choice | **Working** | Template chosen only above a compatibility threshold; features traced to problems and risks |
| 3.2 MVP code generation | **Working** for the 5 templates / **STUBBED** otherwise | Stdlib Python app: API, UI (RTL for Arabic), consented waitlist, SQLite. Ideas no template fits get a spec-only document and Gate 3 STOP, never a forced template |
| 3.3 MVP verification | **Working** | Runs the generated tests (~20) and boots the server |
| Gate 3 | **Working** | Tests must pass; REPEAT rebuilds once; then STOP |
| 4.1 Pricing | **Working** | Competitor prices cited from sources; World Bank affordability cap |
| 4.2 Terms / privacy / refund | **MOCKED** | Templates labelled "not legal advice" |
| 5.1 Launch drafts | **Working** drafts / **STUBBED** posting | Held as `PENDING_FOUNDER_APPROVAL`; never posted |
| 5.2 Checkout → delivery → refund → reconcile | **MOCKED** | Local HMAC simulation; idempotency, revocation, reconciliation tested |
| 6.1 Metrics | **Working** sign-ups / **STUBBED** analytics | Reads the generated MVP's waitlist DB; no visitor analytics |
| 6.2 Decision vs pre-registered rule | **Working** | Reports `INSUFFICIENT_DATA` instead of inventing numbers |
| MVP hosting / deployment | **STUBBED** | Founder runs the generated app locally |
| Founder approval + decision log | **Working** | Token in HttpOnly cookie; every action logged |

## Architecture

A deterministic control plane (`orchestrator.py`, `gates.py`, `approval.py`) owns state, scoring and approvals. An agent plane (`agents/`) does the language work through an open-weight-only gateway (`llm_gateway.py`). `evidence.py` collects sources into a hashed ledger, and its verifier downgrades any claim whose quote isn't in the cited text. The builder assembles the MVP from tested templates in `mvp_templates/` and proves it by running the generated tests in a subprocess. See [ARCHITECTURE.md](ARCHITECTURE.md) for phases, gates, sale-to-cash and data flow.

## Models and free resources

| Model | Weights | How to run free | Used for |
|---|---|---|---|
| `qwen3:8b` (default; any open model via `OLLAMA_MODEL`, e.g. `qwen3:4b`, `llama3.1:8b`, `gemma3:4b`) | Open (Apache-2.0) | Ollama, locally: `docker compose --profile llm up` or your own `ollama pull qwen3:8b` | Intake phrasing, research synthesis, critique, MVP naming and seed content |
| `llama-3.3-70b-versatile` | Open (Llama 3.3 licence) | Groq free tier: set `GROQ_API_KEY` | Fallback for the same steps |
| none | n/a | default when no model is reachable | Rule-based / extractive agents, labelled in every output |

Evidence APIs (`ddgs`, Hacker News Algolia, Wikipedia, World Bank) are free and need no keys. `llm_gateway.is_open_weight` rejects closed-weight model names such as `gpt-*`, `gemini-*` and `claude-*`. The committed demo ran in rule-based / extractive mode (`"model": null` in the log), because no LLM was reachable on the build machine.

## Cost per run

About **$0.00 per run**: a local Ollama model or no model at all, and keyless research APIs. On Groq's free tier it is also $0.00 within the free limits. A run makes at most 5 LLM calls, each with a prompt capped at 40 source passages.

## Demo video

Recording pending; the link will be added here.

## What our system will NOT do

- Promise income, profit or success. Generated text is scanned for income promises and urgency phrases.
- Create fake reviews, testimonials, sign-ups, user counts or countdown timers. Seed content is labelled SAMPLE DATA.
- Pose as the founder, a customer or another brand. Launch drafts are for the founder to post personally.
- Hold, move or refund money, create accounts, or store passwords or card numbers. Payments are a local simulation.
- Publish, send, spend or sign anything without an explicit founder decision recorded in code.
- Work on physical goods, financial / investment / crypto products, or health / medical / legal advice.
- Hide core features behind a paywall. The generated MVP's core is free, and pricing adds capacity only.
- Present an unverified claim as fact, or simulated metrics as real results.

## How the project stays alive after the hackathon

- **Maintainers:** the founding team triages issues and reviews PRs weekly.
- **Roadmap:** more archetypes, and an LLM code-diff mode gated by the generated tests; visitor analytics in the MVP; a sandbox payment connector behind founder approval; Arabic-first regional evidence packs; a CI benchmark of briefs with expected gate outcomes.
- **Community:** MIT-licensed. Adding an archetype means adding one `core.py` plus its tests in `mvp_templates/`, a well-scoped first contribution.
- **Funding:** no paid tier. It runs on free, keyless APIs and local models; community sponsorship only if hosting a public demo becomes necessary.
