# HatchAI walkthrough: commands, scenarios, verification status

**What it is.** A six-phase pipeline (Discover → Validate → Build → Commercial → Sell/deliver/get paid
→ Operate) that takes a founder's brief, collects cited evidence, computes GO / REPEAT / PIVOT / STOP
in code, waits for a founder decision at every gate, and builds and tests a runnable MVP when the
evidence allows. Almost everything is deterministic code; an optional local open-weight LLM drafts two
small text fields in Phase 3. Payments are a local simulation (MOCKED). Cost: $0.

## Commands (Python 3.12, `pip install -r requirements.txt`; or `docker compose up` for the web UI)

| Goal | Command | Network / LLM |
|---|---|---|
| Reproducible demo (3 scenarios) | `python orchestrator.py demo` | none / `LLM_DISABLED` |
| Same, with fresh live research for strong + weak | `python orchestrator.py demo --live` | web / local LLM if running |
| Replay one scenario; exit 0 if gates match the capture | `python orchestrator.py replay evidence_snapshots/repeat_scenario.json` | none / `LLM_DISABLED` |
| Capture a new live scenario | `python orchestrator.py capture "<brief>" evidence_snapshots/<name>.json` | web |
| Check a local open-weight model | `python scripts/verify_llm.py` (set `HATCHAI_LLM_BASE_URL`, `HATCHAI_LLM_MODEL`, `HATCHAI_NO_LLM=0`) | local only |
| Tests | `python -m pytest` (114: 90 functional + 24 LLM protocol tests against a stub server; tests never touch `outputs/`, `decision_log.json` or `evidence_snapshots/`) | none |

Outputs go to `outputs/` (one file per phase and step; `-weak-idea` and `-replay-scenario` suffixes),
the log to `decision_log.json`. Every text output starts with its **Evidence mode** (REPLAY + snapshot
+ capture time, or live) and **LLM mode** line.

## The three committed scenarios (evidence captured live on 2026-11-17, replayed offline)

| Scenario | Gates | What it shows |
|---|---|---|
| **Strong**: STEM flashcards, Egypt (`strong_scenario.json`) | G1–G5 GO | 19 sources from 15 domains; E = 95.0, 5/5 categories verified; V = 4.5 (pre-launch maximum). Price anchor USD 8.75 from cited competitor prices, capped to USD 2.57/month by World Bank income data. MVP *STEM Recall* generated, 23/23 of its own tests pass, server boots. Phase 6: 0 real visitors → `INSUFFICIENT_DATA`; 300 labelled TEST visits shown separately. |
| **Weak**: "generic study notes", no user, no country (`weak_scenario.json`) | G1 STOP | The system says STOP before any build or spend. |
| **REPEAT → GO**: Arabic calligraphy workshop booking, Jordan (`repeat_scenario.json`) | G1 REPEAT → G1 GO → G2–G5 GO | Round 1 too thin (E = 46.5 < 55), so a broader second research round runs and reaches GO. |

## What is and is not verified

| Claim | Status |
|---|---|
| Gate outcomes, E and V are computed by code, and the demo reproduces them exactly | **Verified**: replays match the captures; two consecutive demo runs give identical outputs apart from random order ids, ports and durations |
| Every quote in a VERIFIED claim appears in the fetched source text | **Verified** (citation checker + tests) |
| Source freshness | **Not verified**: fetch times are recorded and displayed but **not scored**; publication dates are not extracted |
| Evidence relevance | **Weak**: keyword-based, and it can overrate thin evidence (the strong and weak briefs both score E = 95.0; the REPEAT scenario's E = 100 rests partly on generic booking statistics) |
| Weak idea is stopped on weak evidence | **No**: the weak scenario stops on the **brief rule** (no target user and no geography), not on its evidence score |
| REPEAT path | **Verified** end to end on real captured evidence (REPEAT → GO scenario) |
| PIVOT path | **Only in fixture tests** (`tests/test_pipeline.py`); no committed real scenario |
| Generated MVP works | **Verified** for 5 templates (each app's own ~23 tests run and its server boots); ideas no template fits get a STOP and a spec only |
| LLM use | Limited to **two Phase 3 tasks** (template-synonym suggestion, name + tagline), validated by code; it cannot write code or change scores or gates. **Disabled in replay** and in the default demo. Client protocol verified with a stub server. **No answer from a real open-weight model has been verified.** |
| `docker compose up` | **Not verified**: Docker could not start on the build machine (`docker compose config` is valid) |
| Demand / traffic numbers | The Phase 6 TEST traffic is **labelled test data, not real demand**; real counts are 0 |
| Payments | **MOCKED** local simulation: idempotency, refund revocation and reconciliation are tested; no real processor |
