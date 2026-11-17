# Phase 1 — Evidence REPLAY check: REPEAT -> GO: Arabic calligraphy workshop booking, Jordan (live capture)

> Evidence mode: REPLAY of evidence_snapshots/repeat_scenario.json (captured 2026-11-17T15:31:37+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)

> This run used **replayed** evidence from `evidence_snapshots/repeat_scenario.json`. Nothing was fetched: the snapshot holds the
> sources a live run collected on **2026-11-17T15:31:37+00:00** (original URLs, passages, fetch times, SHA-256).
> Verification, scoring and all gates were re-computed from that snapshot with the current code.
> Replay reproduces the *decisions*; it does not make the captured evidence stronger or fresher.
> Check the relevance of each verified claim in the research-findings file of this scenario.

**Reproduce:** `python orchestrator.py replay evidence_snapshots/repeat_scenario.json`

## Captured research rounds

| Round | Idea researched | New sources | Verified claims at capture | Synthesis | E at capture |
|---|---|---|---|---|---|
| 1 | A booking app for Arabic calligraphy workshops for adult hobbyists in  | 12 | 3 | extractive | 46.5 |
| 2 | A booking app for Arabic calligraphy workshops for adult hobbyists in  | 12 | 9 | extractive | 100.0 |

## Gate outcomes: capture vs. this replay — MATCH

At capture (live run `capture-6ef8cc82`, final status completed):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
| G1 | 1 | REPEAT | 46.5 | 0.0 |
| G1 | 2 | GO | 100.0 | 0.0 |
| G2 | 2 | GO | 100.0 | 4.5 |
| G3 | 2 | GO | 0.0 | 0.0 |
| G4 | 2 | GO | 0.0 | 0.0 |
| G5 | 2 | GO | 0.0 | 0.0 |

This replay (final status completed):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
| G1 | 1 | REPEAT | 46.5 | 0.0 |
| G1 | 2 | GO | 100.0 | 0.0 |
| G2 | 2 | GO | 100.0 | 4.5 |
| G3 | 2 | GO | 0.0 | 0.0 |
| G4 | 2 | GO | 0.0 | 0.0 |
| G5 | 2 | GO | 0.0 | 0.0 |
