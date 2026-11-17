# Phase 3 — MVP spec and build: STEM Recall

> Evidence mode: REPLAY of evidence_snapshots/strong_scenario.json (captured 2026-11-17T15:52:54+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)

> Flashcards that schedule each review for you (SM-2), for university students in Egypt.

**Status:** generated, tested and booted by the pipeline — 23 tests, 0 failures,
0 errors; smoke test passed. Build attempt 1.

## Archetype

`spaced_repetition` — 'spaced_repetition' scored 6 (matched ['flashcard', 'repetition', 'spaced']), 6 ahead of 'booking' (min score 2, min margin 1). All scores: {'spaced_repetition': 6, 'booking': 0, 'habit_tracker': 0, 'directory': 0, 'course': 0}.

## Features (each traced to a problem or risk, each verified by a generated test)

| Feature | What it does | API action | Traces to |
|---|---|---|---|
| Due-today review queue | Shows only the cards due today, oldest first. | `due` | university students lack an adequate AI-powered flashcard and spaced-repetition study tool. |
| SM-2 adaptive scheduling | Grades 0–5 reschedule each card (1, 6, then ×ease days). | `review` | university students lack an adequate AI-powered flashcard and spaced-repetition study tool. |
| Retention stats | Reviews, average ease and recall rate per user. | `stats` | Key metric: Demand-test sign-up rate; weekly active users; riskiest: Target users will pay a recurring price. |
| Consented waitlist (demand test) | Email + explicit consent; feeds the pre-registered demand test. Nothing is sent automatically. | `waitlist` | Riskiest assumption: Target users will pay a recurring price |

## LLM use (bounded; never code, scores or gate decisions)

- `template_suggestion`: **not_needed (deterministic selection succeeded)**
- `spec_text`: **LLM_DISABLED** — LLM disabled (HATCHAI_NO_LLM=1)

## Data model

Flashcard fields: `front` (text), `back` (longtext), `deck` (text). Seed content: 9 items, **SAMPLE DATA**
(deterministic, derived from the brief).

## Scope

- In: the features above, JSON API, web UI (en, ar, RTL toggle), consented waitlist, free-tier item limit (200).
- Out: accounts/auth, real payments (MOCKED), analytics (STUBBED), hosting/deployment (founder decision).

## Run it

```bash
cd generated_mvps/demo-strong
python server.py --port 8080          # http://localhost:8080
python -m unittest discover -s tests -v
```

Files: README.md, config.json, core.py, index.html, server.py, store.py, tests/test_core.py, tests/test_server.py, tests/test_spec.py
