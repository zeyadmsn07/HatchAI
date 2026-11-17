# Phase 1 — Evidence REPLAY check: capture-5bb3f33f

> Evidence mode: REPLAY of evidence_snapshots/weak_scenario.json (captured 2026-11-17T15:53:01+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

> This run used **replayed** evidence from `evidence_snapshots/weak_scenario.json`. Nothing was fetched: the snapshot holds the
> sources a live run collected on **2026-11-17T15:53:01+00:00** (original URLs, passages, fetch times, SHA-256).
> Verification, scoring and all gates were re-computed from that snapshot with the current code.
> Replay reproduces the *decisions*; it does not make the captured evidence stronger or fresher.
> Check the relevance of each verified claim in the research-findings file of this scenario.

**Reproduce:** `python orchestrator.py replay evidence_snapshots/weak_scenario.json --scoring v1`

## Captured research rounds

| Round | Idea researched | New sources | Verified claims at capture | Synthesis | E at capture |
|---|---|---|---|---|---|
| 1 | An app that sells generic study notes. | 10 | 10 | extractive | 95.0 |

**Captured under v1:** G1:STOP(E=95.0,V=0.0)

**Replayed under v1:** G1:STOP(E=95.0,V=0.0) (run stopped: Founder stopped the run at gate 1)

## Gate outcomes: capture vs. this replay — MATCH

At capture (live run `capture-5bb3f33f`, final status stopped):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
| G1 | 1 | STOP | 95.0 | 0.0 |

This replay (final status stopped):

| Gate | Round | Outcome | E | V |
|---|---|---|---|---|
| G1 | 1 | STOP | 95.0 | 0.0 |
