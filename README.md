# HatchAI: evidence-gated open-source venture builder

An open-source pipeline of cooperating agents, almost all of them deterministic code (an optional local LLM drafts two small text fields), that takes a founder's idea through six gated phases (Discover → Validate → Build → Commercial → Sell/deliver/get paid → Operate). It **generates and tests a runnable, idea-specific MVP**, and recommends **STOP** when the evidence is weak.

- **Evidence by construction:** live, keyless sources (web search, Hacker News, Wikipedia, World Bank). Every quote is re-checked against the fetched text by code; anything unverified is labelled `ASSUMPTION`.
- **Code decides:** evidence and viability scores and GO / REPEAT / PIVOT / STOP are computed in Python; no LLM can touch them. Nothing proceeds without a founder decision enforced in `approval.py`.
- **Phase 3 builds real software:** 5 tested archetypes (SM-2 flashcards, booking, habit tracker, directory, course). The generated app gets its own idea-specific tests, which the pipeline runs before Gate 3 can pass.
- **Optional local open-weight LLM, two bounded tasks:** any OpenAI-compatible local server (Ollama, llama.cpp, vLLM) may draft the MVP's name and tagline and suggest template synonyms. Code validates everything it returns. Every run is labelled `LLM_LIVE`, `LLM_UNAVAILABLE_FALLBACK` or `LLM_DISABLED`. No hosted or paid APIs. Cost: $0.

**Walkthrough:** [`WALKTHROUGH.md`](WALKTHROUGH.md) lists the commands, the three scenarios and what is and is not verified.

**Committed demo** (`python orchestrator.py demo`, outputs in [`outputs/`](outputs/), log in [`decision_log.json`](decision_log.json)) **replays three evidence snapshots captured from live runs on 2026-11-17** ([`evidence_snapshots/`](evidence_snapshots/)). It runs offline and gives the same gate outcomes, scores and outputs on every run; every output is labelled with its evidence mode.
- **Strong brief** (STEM flashcards, Egypt; 19 sources): G1–G5 **GO** with E = 95.0, 5/5 evidence categories verified, V = 4.5. Price anchor USD 8.75 (median of cited competitor prices), entry price USD 2.57/month after the World Bank affordability cap. Its MVP *STEM Recall* passed **23/23** generated tests and booted.
- **Weak brief** ("generic study notes", no user, no country): **Gate 1 STOP**, because the brief names no target user or geography.
- **REPEAT → GO** (Arabic calligraphy workshop booking, Jordan): round 1 is too thin (E = 46.5 < 55), so Gate 1 says **REPEAT**; a broader second round reaches **GO**. The evidence is weak; see [`evidence_snapshots/README.md`](evidence_snapshots/README.md).

These numbers are as of the capture date; `python orchestrator.py demo --live` repeats the research live, so its numbers can differ.

## Quickstart

```bash
docker compose up
```

Open **http://localhost:8000**, submit a brief, and decide each gate (Approve / Repeat / Pivot / Stop, or override with a written reason). Output files and the path of the generated MVP appear on the run page.

Optional extras:

```bash
docker compose --profile llm up          # also starts Ollama and pulls qwen3:8b (~5 GB, once)
python orchestrator.py demo               # reproducible demo: replays the 3 committed snapshots, offline (no Docker)
python orchestrator.py demo --live        # strong + weak scenarios do fresh live research instead (results vary)
python orchestrator.py replay evidence_snapshots/repeat_scenario.json   # one scenario; exits 0 if gates match the capture
python orchestrator.py capture "<brief>" evidence_snapshots/my.json     # live run that saves its evidence for replay
python orchestrator.py run "<brief>"      # CLI run; you approve every gate at the prompt
python demand_test_traffic.py generated_mvps/demo-strong --visitors 300 --signups 20   # labelled TEST traffic
python orchestrator.py measure demo-strong # re-run Phase 6 on the MVP's stored counts
cd generated_mvps/demo-strong && python server.py --port 8080   # run the generated MVP
python -m pytest                          # 114 tests: 90 functional + 24 LLM protocol tests (stub server)
```

Without Docker: `pip install -r requirements.txt && uvicorn app:app` (Python 3.12).

## What works and what is mocked

| Step | Status | Notes |
|---|---|---|
| 1.1 Intake | **Working** | Deterministic parser (no LLM); unstated fields → `UNKNOWN` |
| 1.2 Guardrail 0 | **Working** | Excluded products and trick intents, fail-closed, no override; re-run on pivots |
| Evidence capture / replay | **Working** | Snapshot of the evidence a live run collected; replay re-runs verification, scores and gates offline, labelled REPLAY. The default demo replays all three scenarios |
| 1.3 Evidence collection | **Working** | `ddgs` web, HN Algolia, Wikipedia, World Bank API; ledger with URL + truncated SHA-256. Fetch times are recorded and displayed but **not scored**: source freshness is not verified |
| 1.4 Synthesis + citation verifier | **Working** | Extractive (no LLM): claims are verbatim fetched passages, re-matched to the fetched text |
| Gate 1 | **Working** | E-score; GO / REPEAT (2nd research round) / PIVOT / STOP |
| 2.1 Red-team critique + viability | **Working** | Rule-based critique; V-score computed in code (no LLM) |
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
| 6.1 Metrics | **Working** | Page visits, unique visitors (cookie) and consented sign-ups stored in the MVP's `app.db`; REAL and TEST traffic kept apart. The committed demo has only labelled TEST traffic, so its real counts are 0 |
| 6.2 Decision vs pre-registered rule | **Working** | Thresholds read from the stored demand test; decides on REAL traffic only (`INSUFFICIENT_DATA` below the visitor minimum); TEST traffic shown separately as a pipeline check |
| MVP hosting / deployment | **STUBBED** | Founder runs the generated app locally |
| Founder approval + decision log | **Working** | Token in HttpOnly cookie; every action logged |

## Architecture

A deterministic control plane (`orchestrator.py`, `gates.py`, `approval.py`) owns state, scoring and approvals. An agent plane (`agents/`) does the domain work deterministically. An optional local open-weight model (`llm_gateway.py`, OpenAI-compatible) handles only two text tasks in Phase 3. `evidence.py` collects sources into a hashed ledger, and its verifier downgrades any claim whose quote isn't in the cited text. The builder assembles the MVP from tested templates in `mvp_templates/` and proves it by running the generated tests in a subprocess. See [ARCHITECTURE.md](ARCHITECTURE.md) for phases, gates, sale-to-cash and data flow.

## Models and free resources

| Model | Weights | How to run free | Used for |
|---|---|---|---|
| Any open-weight model on a **local** OpenAI-compatible server: `qwen3:8b` (default), `qwen3:0.6b`, `llama3.2:1b`, `gemma3:1b`, … | Open | Ollama (`ollama pull qwen3:0.6b`), llama.cpp `llama-server`, vLLM or LM Studio on your machine; `docker compose --profile llm up` starts Ollama | Phase 3 only: (1) template-synonym suggestion when no template clears the threshold, (2) MVP name + tagline |
| none | n/a | default; replays and the default demo always run `LLM_DISABLED` | Deterministic name/tagline and keyword-only template choice |

Evidence APIs (`ddgs`, Hacker News Algolia, Wikipedia, World Bank) are free and need no keys. `llm_gateway.is_open_weight` rejects closed-weight model names such as `gpt-*`, `gemini-*` and `claude-*`.

**What the LLM may do, and what it may not.** It never writes code, claims or evidence, and never sets a score or gate. Template suggestion counts only synonyms whose phrase appears verbatim in the idea and maps to an existing keyword of a template that already matched; it adds at most +1, and the usual score and margin thresholds still decide. Name and tagline are length-checked, scanned for forbidden phrases and rejected if they look like code or URLs. Malformed, empty, schema-invalid or timed-out answers (one retry by default) give a labelled `LLM_UNAVAILABLE_FALLBACK`, never a crash. Each output carries an `LLM mode:` line, and the log records `llm_mode_at_start` and every `llm_*` task, with the model name only when a model actually answered.

**Verified vs. not verified.**
- **Verified by protocol tests** (`tests/test_llm_protocol.py`, 24 tests against a local stub server; this is not model verification): request format, `/v1/models` probe, timeout, retry limit, schema validation, fallback on bad output, mode labels, and that LLM output leaves gates, E and V unchanged.
- **NOT VERIFIED:** an answer from a real open-weight model. No model was available on the build machine. The committed demo runs `LLM_DISABLED`.

To check it with your own local model:

```bash
ollama pull qwen3:0.6b && ollama serve          # or: llama-server -m model.gguf --port 8080
export HATCHAI_LLM_BASE_URL=http://localhost:11434/v1 HATCHAI_LLM_MODEL=qwen3:0.6b HATCHAI_NO_LLM=0
python scripts/verify_llm.py                     # exit 0 = VERIFIED round-trip; non-zero = NOT VERIFIED
python orchestrator.py run "<brief>" --yes       # a live run; outputs show 'LLM mode: LLM_LIVE (model ...)'
```

## Cost per run

About **$0.00 per run**: keyless research APIs, and either no LLM or a model running on your own machine. A run makes at most 2 small LLM calls (Phase 3), each capped at 120–200 output tokens.

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
- **Funding:** no paid tier. It runs on free, keyless APIs, with an optional model on the user's own machine; community sponsorship only if hosting a public demo becomes necessary.
