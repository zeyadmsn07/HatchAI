# Phase 3 — MVP spec and build: Arabic Book

> Book sessions without double-bookings or clashes, for early users in Jordan.

**Status:** generated, tested and booted by the pipeline — 23 tests, 0 failures,
0 errors; smoke test passed. Build attempt 1.

## Archetype

`booking` — 'booking' scored 3 (matched ['book', 'booking']), 2 ahead of 'course' (min score 2, min margin 1). All scores: {'spaced_repetition': 0, 'booking': 3, 'habit_tracker': 0, 'directory': 0, 'course': 1}.

## Features (each traced to a problem or risk, each verified by a generated test)

| Feature | What it does | API action | Traces to |
|---|---|---|---|
| Live availability | Remaining seats per session. | `availability` | UNKNOWN (not stated by founder) lack an adequate booking app. |
| Safe booking | Capacity, duplicate and time-clash checks. | `book` | UNKNOWN (not stated by founder) lack an adequate booking app. |
| Self-service cancellation | Frees the seat immediately. | `cancel` | Key metric: Demand-test sign-up rate; weekly active users; riskiest: Target users will pay a recurring price. |
| Consented waitlist (demand test) | Email + explicit consent; feeds the pre-registered demand test. Nothing is sent automatically. | `waitlist` | Riskiest assumption: Target users will pay a recurring price |

## Data model

Session fields: `title` (text), `provider` (text), `start` (datetime), `duration_min` (number), `capacity` (number). Seed content: 2 items, **SAMPLE DATA**
(deterministic, derived from the brief).

## Scope

- In: the features above, JSON API, web UI (en, ar, RTL toggle), consented waitlist, free-tier item limit (200).
- Out: accounts/auth, real payments (MOCKED), analytics (STUBBED), hosting/deployment (founder decision).

## Run it

```bash
cd generated_mvps/demo-replay
python server.py --port 8080          # http://localhost:8080
python -m unittest discover -s tests -v
```

Files: README.md, config.json, core.py, index.html, server.py, store.py, tests/test_core.py, tests/test_server.py, tests/test_spec.py
