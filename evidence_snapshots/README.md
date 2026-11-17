# Evidence snapshots

Each file holds the evidence a **live** HatchAI run actually collected (web search, Hacker News,
Wikipedia, World Bank). `python orchestrator.py replay <file>` re-runs verification, scoring and
every gate from it with no network access and no LLM. The evidence is never edited after capture.

| File | Scenario | Gate outcomes at capture | Notes |
|---|---|---|---|
| `strong_scenario.json` | STEM flashcards, Egypt (`demo-strong`) | G1–G5 GO | Has `capture_metadata` (date, search method, git commit and dirty state) |
| `weak_scenario.json` | "Generic study notes", no user or country (`demo-weak`) | G1 STOP | Has `capture_metadata`. The STOP comes from the brief naming no target user or geography, not from the evidence score |
| `repeat_scenario.json` | Arabic calligraphy workshop booking, Jordan (`demo-replay`) | G1 REPEAT → G1 GO → G2–G5 GO | See below |

The strong and weak snapshots record `uncommitted_changes: true` because they were captured before the checkpoint commit; the evidence is unmodified.

## `repeat_scenario.json`

- **It predates `capture_metadata`.** It has no recorded search method or git commit; only `captured_at`
  and the per-source `fetch_time` values record when it was collected. The `label` field is
  top-level metadata added after capture; the sources and claims are untouched.
- **Hashes:** each source's `text_hash` is the **first 16 hex characters of SHA-256** over the
  cleaned passages HatchAI stored (`" ".join(passages)`), not over the full fetched page. All 24
  match (checked by `tests/test_replay.py::test_committed_snapshot_integrity`).
- **Its evidence is weak.** Round 1 counts a loosely related Hacker News thread as demand. Round 2's E = 100
  rests partly on generic booking-industry statistics and tourist calligraphy classes. The scenario
  shows the REPEAT loop working; it does not show a validated market.

## Freshness

Fetch times are **recorded and displayed but not scored**: the evidence score has no recency
component, and HatchAI does not extract publication dates. A replay reproduces the decisions as
of the capture date; it does not make the evidence any fresher.
