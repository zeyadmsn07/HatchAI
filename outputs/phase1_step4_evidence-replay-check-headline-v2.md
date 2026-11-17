# Phase 1 — Evidence REPLAY check: strong-v2-live

> Evidence mode: REPLAY of evidence_snapshots/strong_v2_scenario.json (captured 2026-11-17T20:51:46+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v2 (relevance: brief-specific user / problem / local terms)

> This run used **replayed** evidence from `evidence_snapshots/strong_v2_scenario.json`. Nothing was fetched: the snapshot holds the
> sources a live run collected on **2026-11-17T20:51:46+00:00** (original URLs, passages, fetch times, SHA-256).
> Verification, scoring and all gates were re-computed from that snapshot with the current code.
> Replay reproduces the *decisions*; it does not make the captured evidence stronger or fresher.
> Check the relevance of each verified claim in the research-findings file of this scenario.

**Reproduce:** `python orchestrator.py replay evidence_snapshots/strong_v2_scenario.json --scoring v2`

## Captured research rounds

| Round | Idea researched | New sources | Verified claims at capture | Synthesis | E at capture |
|---|---|---|---|---|---|
| 1 | An AI-powered flashcard and spaced-repetition study tool for universit | 17 | 8 | extractive | 84.2 |
| 2 | An AI-powered flashcard and spaced-repetition study tool for universit | 10 | 8 | extractive | 84.2 |
| 1 | Narrow the idea to university students in Egypt: An AI-powered flashca | 24 | 7 | extractive | 83.9 |

**Captured under v2:** G1:REPEAT(E=84.2,V=0.0) → G1:PIVOT(E=84.2,V=0.0) → G1:GO(E=83.9,V=0.0) → G2:GO(E=83.9,V=4.0) → G3:GO(E=0.0,V=0.0) → G4:GO(E=0.0,V=0.0) → G5:GO(E=0.0,V=0.0)

**Replayed under v2:** G1:REPEAT(E=84.2,V=0.0) → G1:PIVOT(E=84.2,V=0.0) → G1:GO(E=83.9,V=0.0) → G2:GO(E=83.9,V=4.0) → G3:GO(E=0.0,V=0.0) → G4:GO(E=0.0,V=0.0) → G5:GO(E=0.0,V=0.0)

## Gate outcomes: capture vs. this replay — MATCH

At capture (live run `cap-strong-v2`, final status completed):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
| G1 | 1 | REPEAT | 84.2 | 0.0 |
| G1 | 2 | PIVOT | 84.2 | 0.0 |
| G1 | 1 | GO | 83.9 | 0.0 |
| G2 | 1 | GO | 83.9 | 4.0 |
| G3 | 1 | GO | 0.0 | 0.0 |
| G4 | 1 | GO | 0.0 | 0.0 |
| G5 | 1 | GO | 0.0 | 0.0 |

This replay (final status completed):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
| G1 | 1 | REPEAT | 84.2 | 0.0 |
| G1 | 2 | PIVOT | 84.2 | 0.0 |
| G1 | 1 | GO | 83.9 | 0.0 |
| G2 | 1 | GO | 83.9 | 4.0 |
| G3 | 1 | GO | 0.0 | 0.0 |
| G4 | 1 | GO | 0.0 | 0.0 |
| G5 | 1 | GO | 0.0 | 0.0 |
