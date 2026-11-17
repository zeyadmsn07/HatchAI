# Phase 1 — Evidence REPLAY check: capture-d247e818

> Evidence mode: REPLAY of evidence_snapshots/strong_scenario.json (captured 2026-11-17T15:52:54+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

> This run used **replayed** evidence from `evidence_snapshots/strong_scenario.json`. Nothing was fetched: the snapshot holds the
> sources a live run collected on **2026-11-17T15:52:54+00:00** (original URLs, passages, fetch times, SHA-256).
> Verification, scoring and all gates were re-computed from that snapshot with the current code.
> Replay reproduces the *decisions*; it does not make the captured evidence stronger or fresher.
> Check the relevance of each verified claim in the research-findings file of this scenario.

**Reproduce:** `python orchestrator.py replay evidence_snapshots/strong_scenario.json --scoring v1`

## Captured research rounds

| Round | Idea researched | New sources | Verified claims at capture | Synthesis | E at capture |
|---|---|---|---|---|---|
| 1 | An AI-powered flashcard and spaced-repetition study tool for universit | 19 | 10 | extractive | 95.0 |

**Captured under v1:** G1:GO(E=95.0,V=0.0) → G2:GO(E=95.0,V=4.5) → G3:GO(E=0.0,V=0.0) → G4:GO(E=0.0,V=0.0) → G5:GO(E=0.0,V=0.0)

**Replayed under v1:** G1:GO(E=95.0,V=0.0) → G2:GO(E=95.0,V=4.5) → G3:GO(E=0.0,V=0.0) → G4:GO(E=0.0,V=0.0) → G5:GO(E=0.0,V=0.0)

## Gate outcomes: capture vs. this replay — MATCH

At capture (live run `capture-d247e818`, final status completed):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
| G1 | 1 | GO | 95.0 | 0.0 |
| G2 | 1 | GO | 95.0 | 4.5 |
| G3 | 1 | GO | 0.0 | 0.0 |
| G4 | 1 | GO | 0.0 | 0.0 |
| G5 | 1 | GO | 0.0 | 0.0 |

This replay (final status completed):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
| G1 | 1 | GO | 95.0 | 0.0 |
| G2 | 1 | GO | 95.0 | 4.5 |
| G3 | 1 | GO | 0.0 | 0.0 |
| G4 | 1 | GO | 0.0 | 0.0 |
| G5 | 1 | GO | 0.0 | 0.0 |
