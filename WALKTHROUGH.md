# HatchAI walkthrough: commands, scenarios, verification status

**What it is.** A six-phase pipeline (Discover → Validate → Build → Commercial → Sell/deliver/get paid
→ Operate) that takes a founder's brief, collects cited evidence, computes GO / REPEAT / PIVOT / STOP
in code, waits for a founder decision at every gate, and builds and tests a runnable MVP when the
evidence allows. Almost everything is deterministic code; an optional local open-weight LLM drafts two
small text fields in Phase 3. Payments are a local simulation (MOCKED). Cost: $0.

## Commands (Python 3.12, `pip install -r requirements.txt`; or `docker compose up` for the web UI)

| Goal | Command | Network / LLM |
|---|---|---|
| Reproducible demo (headline scenario captured under v2; 3 earlier scenarios under v1, plus the same 3 replayed under v2) | `python orchestrator.py demo` | none / `LLM_DISABLED` |
| Same, with fresh live research for strong, weak and headline | `python orchestrator.py demo --live` | web / local LLM if running |
| Replay one scenario; exit 0 if gates match the capture (or the difference is a labelled scoring-version difference) | `python orchestrator.py replay evidence_snapshots/repeat_scenario.json [--scoring v1\|v2]` | none / `LLM_DISABLED` |
| Capture a new live scenario | `python orchestrator.py capture "<brief>" evidence_snapshots/<name>.json` | web |
| Check a local open-weight model | `python scripts/verify_llm.py` (set `HATCHAI_LLM_BASE_URL`, `HATCHAI_LLM_MODEL`, `HATCHAI_NO_LLM=0`) | local only |
| Tests | `python -m pytest` (135, all passing on 2026-11-17, including 24 LLM protocol tests against a stub server, 4 evidence-audit tests and 4 Advisor tests; tests never touch `outputs/`, `decision_log.json` or `evidence_snapshots/`) | none |

Outputs go to `outputs/` (one file per phase and step; `-weak-idea` and `-replay-scenario` suffixes),
the log to `decision_log.json`. Every text output starts with its **Evidence mode** (REPLAY + snapshot
+ capture time, or live) and **LLM mode** line.

## The four committed scenarios (evidence captured live on 2026-11-17, replayed offline)

| Scenario | Gates | What it shows |
|---|---|---|
| **Headline**: STEM flashcards, Egypt, captured live under scoring **v2** (`strong_v2_scenario.json`, outputs `*-headline-v2.*`) | G1 REPEAT → G1 PIVOT → G1 GO → G2–G5 GO | Round 1 (E = 84.2) has no passage naming university students + the problem + Egypt, so demand is unverified → REPEAT; a broader round 2 still lacks it → PIVOT to the best-evidenced angle; the pivot reaches GO (E = 83.9, V = 4.0). Pricing stays `ASSUMPTION`. The evidence audit reports 7 cited sources, 56% fresh, 71% independent, competitors backed only by vendor/stale sources, and a 2015 channel source. MVP *STEM Recall*: 23/23 tests pass, server boots. |
| **Strong**: STEM flashcards, Egypt (`strong_scenario.json`) | G1–G5 GO | 19 sources from 15 domains; E = 95.0, 5/5 categories verified; V = 4.5 (pre-launch maximum). Price anchor USD 8.75 from cited competitor prices, capped to USD 2.57/month by World Bank income data. MVP *STEM Recall* generated, 23/23 of its own tests pass, server boots. Phase 6: 0 real visitors → `INSUFFICIENT_DATA`; 300 labelled TEST visits shown separately. |
| **Weak**: "generic study notes", no user, no country (`weak_scenario.json`) | G1 STOP | The system says STOP before any build or spend. |
| **REPEAT → GO**: Arabic calligraphy workshop booking, Jordan (`repeat_scenario.json`) | G1 REPEAT → G1 GO → G2–G5 GO | Round 1 too thin (E = 46.5 < 55), so a broader second research round runs and reaches GO. |

## Scoring v1 vs v2 on the frozen snapshots

Same snapshots, same gate thresholds and logic; only the relevance rule differs (see `ARCHITECTURE.md`, "Relevance rule").
v2 results are in `outputs/*-scoring-v2.*`. A v2 replay stops where it would need research the v1 capture never made.

| Snapshot | v1 (as captured): gates, E, V | v2 (replayed): gates, E, V | Why v2 differs |
|---|---|---|---|
| Strong (STEM flashcards, Egypt) | G1–G5 **GO**; E = 95.0; V = 4.5 | G1 **REPEAT**; E = 84.2; V not reached. Replay stops: round 2 was never captured | No passage names university students + the flashcard/STEM problem + Egypt/Arabic, so demand is unverified |
| Weak ("generic study notes") | G1 **STOP**; E = 95.0 | G1 **STOP**; E = 51.3 | Still STOP on the **brief rule**; the HN EpiPen threads and the local-constraint passages no longer count |
| REPEAT → GO (calligraphy booking, Jordan) | G1 REPEAT (E = 46.5) → G1 GO (E = 100.0) → G2–G5 GO; V = 4.5 | G1 REPEAT (E = 25.3) → G1 **PIVOT** (E = 67.9); V not reached. Replay stops: the pivot idea was never captured | Demand can never verify: the intake recorded no target user (it does not recognise "adult hobbyists"); generic booking statistics no longer count |

## Advisor memos (after Gates 1–3)

Files `phase1_step5_advisor-memo*.md`, `phase2_step4_advisor-memo*.md`, `phase3_step4_advisor-memo*.md`. Each memo states the pain the
verified evidence names, whether the plan or the MVP addresses it, the weakest assumption, evidence-specific risks with kill
criteria, the cheapest test this week, a table that re-runs the gate with each cited source removed, and evidence-based angles.
Every sentence cites a verified source key or says ASSUMPTION; `insight_check.py` deletes the rest and the memo reports how many
were deleted. Key findings on the committed scenarios: the headline GO hinges on one source (removing S12 → REPEAT); the original
strong scenario's MVP covers 0 of 1 verified pains (card preparation, S6), a pain no competitor source mentions.

## What is and is not verified

| Claim | Status |
|---|---|
| Gate outcomes, E and V are computed by code, and the demo reproduces them exactly | **Verified**: replays match the captures; two consecutive demo runs give identical outputs apart from random order ids, ports and durations |
| Every quote in a VERIFIED claim appears in the fetched source text | **Verified** (citation checker + tests) |
| Source freshness and credibility | **Reported, not scored**: publication dates (page metadata, snippet dates, relative dates, API dates), freshness, who is speaking (vendor vs. independent) and quote origin (page vs. search snippet) are audited for every cited source in each findings file. They do not change E or the gates |
| Evidence relevance | **v1 is weak; v2 is stricter, measured below.** v1 (the committed captures) is keyword-based and overrates thin evidence: the weak brief's "demand" was two Hacker News threads about generic EpiPens, and the strong and weak briefs both score E = 95.0. v2 (default for new live runs) needs the brief's own user, problem and local terms. On the same snapshots, the weak brief drops to E = 51.3, and **no snapshot has verified demand any more**. The weak scenario still stops on the brief rule: E = 51.3 alone would mean REPEAT, not STOP. |
| Weak idea is stopped on weak evidence | **No**: the weak scenario stops on the **brief rule** (no target user and no geography), not on its evidence score |
| REPEAT path | **Verified** end to end on real captured evidence (REPEAT → GO scenario) |
| PIVOT path | **Verified on real captured evidence** in the headline scenario (G1 REPEAT → PIVOT → GO), and in fixture tests |
| Generated MVP works | **Verified** for 5 templates (each app's own ~23 tests run and its server boots); ideas no template fits get a STOP and a spec only |
| LLM use | Limited to **two Phase 3 tasks** (template-synonym suggestion, name + tagline), validated by code; it cannot write code or change scores or gates. **Disabled in replay** and in the default demo. Client protocol verified with a stub server. **Verified with a real model on 2026-11-17:** `qwen3:0.6b` via Ollama passed `scripts/verify_llm.py` and the Phase 3 name/tagline task (`LLM_LIVE`). |
| `docker compose up` | **Verified 2026-11-17**: the image builds, `/health` returns ok and the web UI is served on port 8000 |
| Demand / traffic numbers | The Phase 6 TEST traffic is **labelled test data, not real demand**; real counts are 0 |
| Payments | **MOCKED** local simulation: idempotency, refund revocation and reconciliation are tested; no real processor |
