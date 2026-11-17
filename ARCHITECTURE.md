# Architecture: HatchAI, an evidence-gated open-source venture builder

## Overview

HatchAI takes a founder's brief through six phases toward a validated, sellable **digital** product. It has two layers:

* **Control plane (deterministic Python).** `orchestrator.py` is a persisted state machine. `gates.py` computes every gate outcome (GO / REPEAT / PIVOT / STOP) from structured data. `approval.py` enforces founder decisions with a per-run token, and `callbacks.py`/`db.py` append every agent action to the decision log. **No LLM can score, approve, publish or advance a run.**
* **Agent plane (`agents/`).** Intake, research synthesis, critique, canvas and demand test are deterministic. An optional LLM does exactly two bounded text tasks in Phase 3 (see **LLM use**). That model must be **open-weight** and served **locally** by any OpenAI-compatible server (Ollama, llama.cpp, vLLM; default `qwen3:8b`). Closed-weight names are refused in code (`llm_gateway.is_open_weight`), and there is no hosted provider. With no model, the deterministic text is used and labelled, so the full pipeline still runs at USD 0.

The key design choice is that **code decides**. Evidence is collected by code, quotes are re-verified by code, and scores are computed by code. The MVP is assembled from tested templates and then proven by actually running its tests.

```mermaid
graph TD
    B[Founder brief] --> G0{Guardrail 0<br/>fail-closed, no override}
    G0 -->|excluded / trick intent| X[Blocked + logged]
    G0 --> P1[Phase 1 Discover<br/>intake, live evidence, citation verifier]
    P1 --> GT1{Gate 1 + founder}
    GT1 -->|repeat: broader round| P1
    GT1 -->|pivot: best-evidenced angle| P1
    GT1 -->|stop| S1[STOP: don't launch this]
    GT1 -->|go| P2[Phase 2 Validate<br/>critique, code-computed viability, canvas, demand test]
    P2 --> GT2{Gate 2 + founder}
    GT2 -->|repeat| P1
    GT2 -->|pivot| P1
    GT2 -->|stop| S2[STOP]
    GT2 -->|go| P3[Phase 3 Build<br/>generate MVP, run its tests, boot it]
    P3 --> GT3{Gate 3 + founder}
    GT3 -->|repeat: rebuild without LLM text| P3
    GT3 -->|go| P4[Phase 4 Commercial<br/>evidence-anchored pricing, policy templates]
    P4 --> GT4{Gate 4 + founder}
    GT4 -->|go| P5[Phase 5 Launch + sale-to-cash<br/>drafts held, MOCKED payments]
    P5 --> GT5{Gate 5 + founder}
    GT5 -->|go| P6[Phase 6 Operate<br/>real metrics vs pre-registered rule]
```

## Phases

### Phase 1: Discover

* **Agents:** `agents/intake.py` and `agents/researcher.py`. **Tools:** `evidence.py` (collectors, ledger, verifier).
* **Method:**
  1. **Intake.** A deterministic parser extracts the target user, geography, skills, budget, hours, values and language. Any field the founder did not state is written as `UNKNOWN` and listed in `unknown_fields`. An optional LLM can rephrase stated fields, but cannot turn a guess into a fact: unstated fields keep an `ASSUMPTION` prefix.
  2. **Guardrail 0** runs on the brief, and again on any pivot idea.
  3. **Evidence collection (no LLM, keyless, free).** Category queries are sent to web search via `ddgs` (several backends tried in turn), Hacker News (Algolia API), Wikipedia (MediaWiki API) and the World Bank Indicators API (internet use and GDP per capita for the detected country). Pages are fetched and the best sentences are kept. Lines that look like prompt injection are dropped and ad-redirect URLs are filtered. Each source enters a **ledger** with key `S1..Sn`, URL, title, domain, fetch time, SHA-256 of the text, collector and category.
  4. **Synthesis (no LLM).** Claims feed the evidence score, so they are code-derived: *extractive mode* turns the most relevant passages into claims verbatim. Snapshots captured with LLM-written claims by older versions replay those stored claims. A passage qualifies only if it matches both idea terms and the category's vocabulary and is not navigation text.
  5. **Evidence quality audit (advisory).** For every source a verified claim relies on, `evidence.quality_report` records the publication date (page HTML metadata such as `article:published_time` / JSON-LD `datePublished` / `<time>`, the date at the start of a search snippet including relative dates like "8 hours ago", HN post dates, World Bank data years), freshness at fetch time (fresh ≤ 18 months, aging ≤ 36, stale), who is speaking (`official-statistics`, `academic`, `reference`, `community`, `independent-web`, or `vendor (self-interested)` when the site's own brand appears in the text or the URL is a pricing page) and whether the quote came from the fetched page, the search snippet or an API (`Source.passage_origins`). It lists the categories backed only by vendor or stale evidence and prints warnings. It is shown in every findings file but is **not part of E**, so older captures replay to identical gates.
  5b. **Citation verifier.** Unknown keys are dropped. Each quote must occur in a passage of a cited source (normalised substring or ≥ 0.9 fuzzy window). Claims that fail become `ASSUMPTION (citation not verified)`. Categories with no verified claim get an explicit `ASSUMPTION` placeholder.
  6. **Capture and replay (reproducibility).** A live run started with capture (`python orchestrator.py capture "<brief>" <file>`) saves, for every research round, the exact `Source` records it collected (key, URL, title, domain, original fetch time, SHA-256, passages, collector, category), the raw claims and angles before verification, the verified claims, and the round's E-score. The file also holds the gate outcomes. `python orchestrator.py replay <file>` loads each round's sources from the snapshot instead of calling the collectors, with network access and LLMs switched off. It re-runs the unchanged verifier, scoring and gates, and writes `phase1_step4_evidence-replay-check.md`, which compares the replayed gate outcomes with the captured ones; the command exits non-zero if they differ. A round missing from the snapshot fails the run; replay never falls back to live search. Replayed runs say **Evidence mode: REPLAY** in the findings and Gate 1 files, and log `replay_evidence_round_N` (not `collect_evidence_round_N`) with the original source URLs.
  7. **Research-tool health.** In a live round every collector call is classified as *returned results*, *worked but empty* or *failed* (raised: HTTP 429, timeout, DNS, ...). `evidence.tool_health` marks an **outage** when at least half the calls failed and fewer than 6 new sources came back. Gate 1 then answers REPEAT ("research tools unavailable, retry") while the round budget lasts, and after it judges only what earlier rounds collected, labelling any STOP **INCONCLUSIVE** ("not a verdict on the idea"). A tool failure is never scored as weak evidence. Replays are never in outage.
  8. **Strategist (`agents/strategist.py`).** Ranks pivot candidates built from gaps the verified evidence shows: `pain_gap` (a verified demand source names a pain that no verified competitor source mentions), `localisation` (competitor sources never mention the founder's place or language, while another source does), `price_gap` (median cited competitor price above 1 % of monthly GDP per capita) and `institutions` (a verified source names institutions that serve the user). Score = gap weight (4 / 3 / 3 / 1) + number of distinct source keys behind it. The best candidate becomes `opportunity_angles[0]`, which Gate 1/2 use as the pivot; its angle text is stored as `pivot_evidence` and printed under the pivot. With no evidence-backed candidate it falls back to narrowing the brief, labelled as such. Snapshots captured before the Strategist (`angles_version` 1) replay with their captured pivot text, because their pivot round was collected for it.
* **Output:** `phase1_step1_intake.md`, `phase1_step2_research-findings.md` (claims with links, evidence-score breakdown, ledger, evidence mode) and `phase1_step3_sources.json`; replays add `phase1_step4_evidence-replay-check.md`.

### Phase 2: Validate

* **Agent:** `agents/validator.py`.
* **Method:** The critique is written from the evidence: willingness to pay cites the price range and the source keys of the competitor prices found (and says those are vendor prices, not this segment's), demand cites its source and the pain it names (high risk when it rests on one source), competitors name the incumbents' source keys, and channels and local constraints quote what their source says. A category without verified evidence becomes an `ASSUMPTION` risk. Every risk has a falsifiable kill criterion, and willingness to pay is always treated as untested. **Viability (1–5) is computed in code** (`gates.compute_viability`): base 1, verified demand +1, verified competitors / pricing / local constraints +0.5 each, build skills +0.5, ≥ 5 h/week +0.25, all risks testable +0.25, demand test passed +0.5 (always 0 before launch, so pre-launch V ≤ 4.5). The Lean Canvas links each block to the source keys of verified claims, or labels it `ASSUMPTION`. The demand test is **pre-registered** (GO ≥ 10 % sign-up from ≥ 300 visitors, STOP < 3 %, 14 days, cost ≤ 10 % of budget) with `status: NOT_RUN`.
* **Output:** `phase2_step1_critique.md`, `phase2_step2_lean-canvas.md`, `phase2_step3_demand-test-plan.md`.

### Phase 3: Build

* **Agent:** `agents/builder.py`. **Templates:** `mvp_templates/` (stdlib-only Python).
* **Method:**
  1. **Template choice with a compatibility threshold.** Keywords score the idea against each template (strong keyword = 2, weak = 1, each counted once). A template is chosen only if it scores ≥ 2 and beats the runner-up by ≥ 1 (`config/gates.yaml`). Otherwise there is **no default**: no code is generated, `phase3_step1_mvp-spec.md` becomes an `UNSUPPORTED — spec only (STUBBED)` document explaining why, and Gate 3 recommends STOP. Ideas that fit two templates equally are treated as ambiguous and also rejected. Each archetype has real domain logic and unit tests: `spaced_repetition` (SM-2 scheduling, due queue, stats), `booking` (capacity, duplicate and clash checks, cancellation), `habit_tracker` (idempotent check-ins, streaks, weekly targets), `directory` (ranked search, filters, rate-limited inquiries), `course` (ordered lessons, minute-weighted progress, certificates).
  2. **AppSpec**: product name, fields, a feature list where each feature is traced to a verified pain (`Verified pain S6: '…'`) when it shares terms with it, otherwise to an `ASSUMPTION (job to be done)` stated per archetype, a key metric or the riskiest assumption (never to a restatement of the idea). If the evidence names a pain that no feature solves, the builder adds a **pain question to the waitlist** (`AppSpec.pain_question`): visitors may answer it when they sign up, the answer is stored with the consented sign-up, and the Advisor reports that pain as *measured by the demand test*, not as covered, and sample seed content derived from the brief (for example, bilingual Arabic/English STEM cards for an Arabic STEM brief). Seeds are deterministic. An optional LLM may draft only the name and tagline (see **LLM use**).
  3. **Render** to `generated_mvps/<run>/`: SQLite store, JSON API, web UI (with an RTL toggle when Arabic is requested), page-visit counting and a consented waitlist that are the demand-test instrument (REAL vs TEST traffic labelled), a free-tier item limit, and an **idea-specific `tests/test_spec.py`** with one test per feature.
  4. **Verify for real**: `python -m unittest discover` runs in a subprocess (about 20 tests: domain, HTTP integration, spec). Then `server.py` is booted on a free port and `/health` and `/api/items` are checked.
* **Output:** `phase3_step1_mvp-spec.md`, `phase3_step2_mvp-source.md` (idea-specific source shown in full), `phase3_step3_mvp-test-report.txt` (raw test output).

### Phase 4: Commercial setup

* **Agent:** `agents/commercial.py`.
* **Method:** Monthly prices (`$x/month`) are extracted from fetched passages, and each one keeps its source URL. Anchor = median. Entry price = 50 % of the anchor (`ASSUMPTION`), capped at 1 % of monthly GDP per capita when the World Bank row was fetched. The core stays free, and paid tiers add capacity only. Terms, privacy and refund templates are labelled *MOCKED, not legal advice*.
* **Output:** `phase4_step1_pricing.md`, `phase4_step2_policies.md`.

### Phase 5: Sell, deliver, get paid

* **Method:** The launch copy is drafted in the founder's voice, with no testimonials, counts, countdowns or promises, and stays `PENDING_FOUNDER_APPROVAL`. Nothing is ever posted. The sale-to-cash path runs as a **MOCKED** local simulation priced at the Phase 4 Plus tier (see Sale to cash).
* **Output:** `phase5_step1_launch-drafts.md`, `payment_test_log.md`.

### Phase 6: Operate and learn

* **Agent:** `agents/operate.py`.
* **Method:** Reads stored counts only, using the generated MVP's own `Store.metrics()` on its `app.db`: page visits, unique visitors (random `hatchai_vid` cookie) and consented waitlist sign-ups, plus test-mode orders and refunds. Thresholds (minimum unique visitors, GO and STOP sign-up rates) come from the `DemandTest` stored in Phase 2. `decide()` (INSUFFICIENT_DATA / PERSEVERE / PIVOT / STOP) is applied to **real traffic only**.
* **TEST traffic:** `demand_test_traffic.py` starts an MVP and sends visits and sign-ups that carry `X-HatchAI-Traffic: TEST`, `test-` visitor ids and `@example.com` addresses; the MVP stores them as TEST events. Phase 6 shows them in a separate "pipeline check, NOT demand" section and never uses them in the decision. `python orchestrator.py measure <run>` re-runs Phase 6 on a completed run. The committed demo sends 300 TEST visitors and 20 TEST sign-ups: real counts stay 0, so the decision is `INSUFFICIENT_DATA`. A table labelled `SYNTHETIC` still shows how the rule decides on hypothetical inputs.
* **Output:** `phase6_step1_operate-memo.md`.

### LLM use (all phases)

**Why the LLM was removed from intake, research and critique.** Earlier versions let a model rewrite brief fields, write the research claims and add critique risks. Research claims feed the evidence score E, and critique risks fed the "risks testable" part of viability V, so model output could move the numbers the gates decide on. The model's answers were also not reproducible. These steps are now deterministic. The prompt files they used were deleted: `prompts/intake.md`, `prompts/researcher.md` and `prompts/validator.md`. The remaining prompts are `prompts/builder.md` (name and tagline) and `prompts/template_suggester.md`.

The LLM calls are in Phase 3 and in the optional Advisor summary, through `llm_gateway.complete_json`: one OpenAI-compatible client (`POST {base}/chat/completions` with strict JSON-schema output, `GET /models` as a probe). Providers: **local** (default; `HATCHAI_LLM_BASE_URL`, `HATCHAI_LLM_MODEL`) or, opt-in, **Groq's free tier** (`HATCHAI_LLM_PROVIDER=groq`, `GROQ_API_KEY`, default `openai/gpt-oss-120b`), which serves open-weight models only. `HATCHAI_LLM_TIMEOUT` (60 s) and `HATCHAI_LLM_RETRIES` (1) apply to both. Closed-weight names are refused on every provider. `strict_schema` sets `additionalProperties: false` and full `required` lists so strict servers accept the schema; a server that rejects schema mode gets JSON mode once, and HTTP 429 is retried after its `retry-after`. Nothing requires payment.

| Task | When | What code accepts |
|---|---|---|
| `template_suggestion` | only if no template clears the threshold by keywords | synonym pairs whose phrase is in the idea verbatim and whose keyword belongs to a template that already has a keyword match; +1 at most; the same `min_template_score` and `min_template_margin` then decide |
| `spec_text` | build attempt 1 | product name ≤ 5 words / 40 chars and tagline ≤ 140 chars, no code or URLs, no forbidden phrases |

Every response is schema-validated. Timeouts, HTTP errors, and empty, malformed or schema-invalid answers are retried once and then become `LLM_UNAVAILABLE_FALLBACK`, so the deterministic text or choice is kept. The run's mode (`LLM_LIVE`, `LLM_UNAVAILABLE_FALLBACK` or `LLM_DISABLED`) is probed at run start, logged as `llm_mode_at_start`, and shown on an `LLM mode:` line in every Markdown/text output. Each task is logged as `llm_<task>` with the model name only when a model answered. Replays and the default demo force `LLM_DISABLED`. The LLM cannot write code, evidence or claims, and cannot change E, V or any gate. Protocol tests: `tests/test_llm_protocol.py` (stub server). Real-model check: `python scripts/verify_llm.py`; verified with `qwen3:0.6b` (local) and `openai/gpt-oss-120b` (Groq free tier) on 2026-11-17.

## Gates

All thresholds live in `config/gates.yaml`. Each gate writes `phaseN_gate_decision.md` with its checks and the gate history of the run, then **waits for a founder decision** (`approval.py`):

| Gate outcome | Founder may choose |
|---|---|
| GO | approve, stop |
| REPEAT | repeat, stop, override (written reason) |
| PIVOT | pivot, stop, override (written reason) |
| STOP | stop, override (written reason) |

Guardrail 0 blocks create no gate record, so they cannot be overridden.

**Evidence score E (0–100), verified claims only:** category coverage 40, verified ratio 25, cited-domain diversity 20, source-type triangulation (web / HN / Wikipedia / World Bank) 15. There is **no recency component in E**: publication dates and freshness are extracted and reported in the evidence quality audit (Phase 1, step 5), but they do not change the score. Folding the audit into a v3 score is on the roadmap.

**Relevance rule: scoring versions.** E is computed the same way in both versions. The versions differ only in which fetched passages count as verified claims (`evidence.extractive_claims`). Gate thresholds and gate logic are identical. Every output shows `Scoring version: v1|v2`, every log entry carries `scoring_version`, and snapshots record the version they were captured under.

* **v1** (committed snapshots; replays default to the snapshot's own version): a passage counts for a category if it contains any of the first 10 idea/target keywords (substring match) **and** any word from that category's vocabulary. This lets thin evidence through. Every Hacker News passage contains "points and", which was demand vocabulary, so a thread sharing one generic word with the idea counted as demand. Generic words such as "study", "booking" and "generic" were enough to match.
* **v2** (default for new live runs; `HATCHAI_SCORING` overrides it): the passage must match the brief's own terms, using whole-word prefix matches.
  * **User terms** come from the stated target user.
  * **Local terms** come from the stated geography plus any non-English language in the brief.
  * **Product/problem terms** are the idea's keywords minus generic product words (app, tool, platform, AI, sell, generic…) and minus the user and local terms.

  | Category | v2 counts a passage only if… |
  |---|---|
  | demand | ≥1 user term, ≥1 product term, ≥1 local term and demand vocabulary (HN "points and" no longer counts); aggregate industry statistics (million/billion/statistics/market size/industry/global) never count as demand |
  | competitors, pricing | category vocabulary, plus ≥2 product terms, or ≥1 product term and ≥1 user term ("about this product") |
  | local constraints | World Bank rows for the brief's own country, or a local term plus local-constraint vocabulary |
  | channels | channel vocabulary plus ≥1 user or local term |

  A brief with no stated target user or geography can therefore never have verified demand.

  The rule was written before it was run on the snapshots and has not been tuned to them. Replaying a v1 snapshot under v2 (`replay … --scoring v2`) is reported as a labelled scoring-version difference. If v2 needs a research round or pivot the snapshot never captured, the replay stops and says so; it does not invent evidence. Results are in `outputs/*-scoring-v2.*` and in the table in `WALKTHROUGH.md`.

* **Gate 1:** **Tool outage first:** if the live round's research calls mostly failed (`research_tools_available` ✗), **REPEAT** with "research tools unavailable, retry" while `round < 2`; after that, the gate judges only earlier rounds and labels a STOP **INCONCLUSIVE** (not a verdict on the idea). **STOP** if the brief names neither a target user nor a geography, or if E < 25 after the retry budget. **GO** if E ≥ 55, demand is verified and ≥ 3 cited domains. **REPEAT** (broader, rephrased queries; the ledger is merged) while `round < 2`. **PIVOT** to the Strategist's best evidence-backed direction once retries are exhausted and E ≥ 25 (max 1 pivot), with the angle and its source keys printed as *Why this pivot*. Otherwise STOP. When the Advisor's counterfactuals show that removing one source would overturn a GO, the gate file adds an advisory **"this GO is fragile"** note (the outcome itself is unchanged).
* **Gate 2:** **STOP** if E < 35 or V < 2. **GO** if E ≥ 55, V ≥ 3 and every high-risk assumption has a kill criterion. **PIVOT** when evidence is good but V < 3. **REPEAT** (another research round) while budget remains. Otherwise STOP.
* **Gate 3:** **STOP** at once if no tested template fits the idea; a rebuild cannot change that. The founder may stop, or override with a written reason to continue planning without an MVP. Otherwise GO only if files were generated, ≥ 6 generated tests ran with 0 failures and 0 errors, every feature is traced, the server smoke test passes and no forbidden phrase appears. A failure means **REPEAT** (rebuild without LLM seed content); a second failure means **STOP**.
* **Gate 4:** pricing tiers with a free core tier, terms, privacy, refund, the "not legal advice" label, and no income promises (output scanner).
* **Gate 5:** idempotency, revocation and reconciliation all PASS, launch drafts are held for approval, and they contain no forbidden phrases.

**When the system recommends STOP on weak evidence:** the committed demo's weak brief ("generic study notes", no user, no country, no budget) is stopped at Gate 1 before any spending. The tests (`tests/test_pipeline.py`) also run REPEAT → GO and REPEAT → PIVOT → REPEAT → STOP end to end.

**Reproducible REPEAT scenario (committed):** `evidence_snapshots/repeat_scenario.json` was captured from a live run of an Arabic calligraphy workshop booking idea in Jordan. Round 1 reached E = 46.5 (verified demand and local constraints only), so Gate 1 recommended **REPEAT**; the broader round 2 reached GO, and the run completed. To reproduce it offline: `python orchestrator.py replay evidence_snapshots/repeat_scenario.json`. Its outputs are in `outputs/*-replay-scenario.*` and its log entries in `decision_log.json` under `run_id: demo-replay`. Caveat: some verified claims in this scenario are only loosely relevant (e.g. generic booking-industry statistics). Replay reproduces the decision; it does not vouch for the claims.

**Reproducible demo.** `python orchestrator.py demo` replays the headline snapshot `evidence_snapshots/strong_v2_scenario.json` (strong brief captured live under scoring v2 → G1 REPEAT → PIVOT → GO → G2–G5 GO; outputs `*-headline-v2.*`) and the three earlier committed snapshots (`evidence_snapshots/strong_scenario.json` → G1–G5 GO, `weak_scenario.json` → G1 STOP, `repeat_scenario.json` → REPEAT → GO), all captured live on 2026-11-17, offline and without an LLM. Two consecutive runs give identical gate outcomes, E and V scores, output files and decision log. The only exceptions are timestamps, the random order ids in the two payment logs, and the server port and test duration in the two MVP test reports (`tests/test_demo.py`). `python orchestrator.py demo --live` runs the strong and weak scenarios with fresh live research instead; their numbers then depend on the search results of the day. Every Markdown/text output starts with an evidence-mode line (REPLAY with snapshot and capture time, or live), and the log records `replay_evidence_round_N` or `collect_evidence_round_N` ("LIVE collection in this run"). New snapshots: `python orchestrator.py capture "<brief>" evidence_snapshots/<name>.json`.

## Sale to cash

**Status: MOCKED.** There are no processor SDKs and no keys, and no money is held or moved. Code: `payments.py`, `delivery.py`, `refunds.py`, `reconcile.py`.

```mermaid
sequenceDiagram
    participant Buyer as Test buyer
    participant Pay as payments.py
    participant Del as delivery.py
    participant Ref as refunds.py
    participant Rec as reconcile.py
    Buyer->>Pay: checkout.completed {order_id, idempotency_key} + HMAC
    Pay->>Pay: verify HMAC; event_id = idempotency_key (PRIMARY KEY)
    Pay->>Del: issue_entitlement(order) (idempotent per order)
    Buyer->>Pay: same event replayed
    Pay-->>Buyer: duplicate_replay, original token, no second delivery
    Buyer->>Ref: refund (simulated; real refunds are issued by the founder)
    Ref->>Del: entitlement REVOKED, token invalid
    Rec->>Rec: orders x events x settlement lines (gross, fee, refund, payout)
```

1. **Payment triggers delivery:** a verified `checkout.completed` event marks the order PAID and issues one access token.
2. **Refund revokes access:** `check_entitlement` returns `token revoked` afterwards.
3. **Idempotency:** the event id is the idempotency key. A replay returns the original receipt and token, and a forged signature is rejected.
4. **Reconciliation:** every PAID or REFUNDED order must have its payment event and a settlement line (fee schedule 2.9 % + 1.00 is an `ASSUMPTION`). Amounts are integer minor units. Gate 5 fails on any mismatch.

## Data flow

```text
brief ─► intake (parser)     ─► FounderBrief ──────────────────────────────┐
             │                                                                 │
             ▼                                                                 │
   evidence.collect ─► Source ledger (url, sha256, collector, category)        │
             │                                                                 │
             ▼                                                                 ▼
   synthesis [extractive]     ─► verify_claims ─► ResearchFindings ─► Gate 1 (E)
                                                        │
                                                        ▼
   validator ─► Critique (V by code) + LeanCanvas (source keys) + DemandTest ─► Gate 2
                                                        │
                                                        ▼
   builder ─► AppSpec ─► generated_mvps/<run>/ ─► unittest + smoke ─► Gate 3
                                                        │
                                                        ▼
   commercial ─► pricing (cited prices, World Bank cap) + policies ─► Gate 4
                                                        │
                                                        ▼
   launch drafts (held) + payments/delivery/refunds/reconcile ─► Gate 5
                                                        │
                                                        ▼
   operate ─► app.db visits + sign-ups (REAL | TEST) + test orders ─► stored DemandTest rule (REAL only) ─► memo

Every step: callbacks.log ─► SQLite decision_log ─► decision_log.json (demo runs)
Every gate: founder decision via approval.py (token) ─► orchestrator.advance_after_gate
State per run: runs/<run>/state/*.json; outputs: runs/<run>/outputs/ (demo runs: outputs/)
```

### Advisor (after Gates 1, 2 and 3)

* **Agent:** `agents/advisor.py`. **Tools:** `evidence.quality_report`, `evidence.pain_signals`, `builder.coverage`, the gate functions in `gates.py`, `insight_check.py`, optional `llm_gateway` with `prompts/advisor.md`.
* **Method:** reads the stored brief, findings, critique, demand test and MVP features. (1) Pain: the problem wording in verified demand quotes (cue words such as burden, struggle, spend, minus the idea's own words). (2) Plan fit: pain terms matched against the idea (Gates 1–2) or the MVP's features (Gate 3), giving "covers X of Y verified pains". (3) Weakest assumption and evidence-specific risks from the audit (vendor-only pricing, stale sources, snippet-only quotes), each with a kill criterion. (4) Cheapest test this week. (5) Counterfactuals: the same gate function re-run with each cited source removed. (6) Evidence-based angles: a pain competitor sources never mention, a place or language they never mention, and the gap between the competitor median price and the World Bank affordability cap; an angle with no source key is dropped.
* **Rules:** every sentence must cite a verified source key or say ASSUMPTION; `insight_check.check_lines` deletes the rest and the count is printed in the memo. The memo is advisory: E, V, gate outcomes and the gate's own pivot target are unchanged, so replays stay exact. An optional model-written summary (`HATCHAI_ADVISOR_LLM=1`) sees only verified quotes and goes through the same check in a **generate → verify → revise** loop: sentences the checker rejects go back to the model once, with the reason and the allowed keys, and only sentences that pass the code check are shown. Angles come from the Strategist, the same ranked list the gate's pivot is drawn from.
* **Output:** `phase1_step5_advisor-memo.md`, `phase2_step4_advisor-memo.md`, `phase3_step4_advisor-memo.md`, plus an advisory coverage line in `phase3_gate_decision.md`; shown beside the gate buttons in the web UI.

## Built vs. stubbed

| Part | Status |
|---|---|
| Guardrail 0, output scanner, gates 1–5, founder approval, decision log | Working |
| Live evidence collection (web, HN, Wikipedia, World Bank), citation verifier | Working |
| Evidence capture and offline replay (snapshot, labelled REPLAY, capture-vs-replay check) | Working |
| Intake, research synthesis, critique (deterministic, no LLM) | Working |
| Strategist pivot ranking; research-tool health and outage handling at Gate 1 | Working |
| Optional free-tier hosted open-weight models (Groq) | Working, opt-in; verified 2026-11-17 with `openai/gpt-oss-120b` |
| Local open-weight LLM client (OpenAI-compatible) and its 2 bounded tasks | Working protocol (24 stub-server protocol tests); **Verified 2026-11-17** with `qwen3:0.6b` via Ollama (`scripts/verify_llm.py` and the Phase 3 name/tagline task, `LLM_LIVE`) |
| Code-computed viability, Lean Canvas with source keys, pre-registered demand test design | Working (the demand test itself is NOT run) |
| MVP generator: 5 archetypes, idea-specific spec and tests, real test run and boot | Working |
| Evidence-anchored pricing | Working |
| Policy templates | MOCKED (templates, not legal advice) |
| Launch drafts | Working drafts; publishing STUBBED (never posted) |
| Checkout, webhook, delivery, refund, reconciliation | MOCKED (local HMAC simulation) |
| Visit and sign-up measurement read in Phase 6 (REAL vs TEST) | Working; no real traffic in the committed demo |
| Hosting or deployment of the generated MVP | STUBBED (founder runs it locally) |

## Roadmap

1. More archetypes (marketplace with two-sided onboarding, content subscriptions), plus an LLM-assisted code-diff mode gated by the same generated tests.
2. Visitor analytics in the generated MVP, so Phase 6 can apply the full sign-up-rate rule.
3. A sandbox payment connector (e.g. a processor's test mode) behind the existing `payments.py` interface and founder approval.
4. Regional evidence packs: local-language queries (Arabic first) and national statistics APIs.
5. A public evaluation harness: benchmark briefs with expected gate outcomes, run in CI.
