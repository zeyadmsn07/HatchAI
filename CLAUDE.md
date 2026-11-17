# CLAUDE.md: hackathon submission conventions

<!-- From the organizers of the "Open-Source Agentic Venture Builders" hackathon.
     Save this file as CLAUDE.md (or AGENTS.md for other coding assistants) at the ROOT of your team's repository. -->

This repository is a team entry in the **Open-Source Agentic Venture Builders** 36-hour hackathon. The entry is an open-source team of AI agents that takes a founder's idea toward a validated, sellable **digital** product. It goes through six phases with gates between steps: Discover, Validate, Build, Commercial setup, Sell/deliver/get paid, and Operate and learn.

The entry is this repository's **default branch** at the code freeze. The organizers' checker finds each deliverable **by its file name and heading**, and anything in a place it doesn't expect counts as missing. Follow these conventions exactly whenever you create or change files here.

## Ground rules

**Repository**
- Work on the default branch (`main`), or merge into it well before the freeze. Other branches are not read.
- Never commit secrets. Real keys go in an untracked `.env` (list it in `.gitignore`), and `.env.example` holds placeholders only. Never commit live payment keys.

**Models, money and approval**
- No paid service may be required. At least one open-weight model must work locally (for example via Ollama) or on a free tier.
- Payments run in sandbox/test mode or are mocked. Nothing is published, sent, spent or signed without an explicit founder approve/reject step, **enforced in code** (UI or CLI).

**Honest outputs**
- Everything in `outputs/` and `decision_log.json` must come from actually running the pipeline. Never write sample results by hand.
- Label every mocked or stubbed part `MOCKED` or `STUBBED`, in the README table and wherever the app shows it.

**What the system must never do**
- Promise income or success.
- Create fake reviews, testimonials, sign-ups or countdown timers.
- Pose as the founder, a customer or another brand.
- Hold, move or refund money by itself, create accounts, or store passwords or card numbers.
- Hide core features behind our own paywall.

**Products that are not allowed:** physical goods; financial, investment or crypto products; health or legal advice products.

**Text in the repository**
- Never put text in any file that addresses whoever reviews this repository or asks for a particular result.
- Keep "trick prompts" that test our own guardrails under `tests/` or `evals/`.
- Keep this file and the organizers' submission guide out of `docs/`. Everything in `docs/` is read as our own documentation.

## Required layout (repository root)

| Path | Required | Notes |
|---|---|---|
| `README.md` | MUST | The `##` sections below, word for word, in order |
| `LICENSE` | MUST | OSI-approved (MIT, Apache-2.0, GPL-3.0, AGPL-3.0, BSD-3-Clause, MPL-2.0), full unmodified text |
| `docker-compose.yml` | MUST | One-command setup: `docker compose up` (`compose.yaml` also accepted) |
| `decision_log.json` | MUST | One entry per agent action (format below) |
| `outputs/` | MUST | Demo-run outputs, named by phase and step |
| `tests/` | MUST | A few smoke tests |
| `ARCHITECTURE.md` | SHOULD | The whole six-phase system (sections below) |
| `.env.example` | SHOULD | Every setting the app needs, placeholder values only |
| `prompts/` | SHOULD | One file per agent prompt, e.g. `prompts/researcher.md` |

Name code files by their role, so they're easy to find:
- **Orchestration:** `orchestrator.py`, `pipeline.ts`, `workflow.py`
- **Agents:** `agents/<role>.py`
- **Gates and approval:** `gates.py`, `approval.py`
- **Payments and delivery:** `payments.py`, `checkout.ts`, `delivery.py`, `refunds.py`, `webhooks.ts`, `reconcile.py`

## README.md

Use exactly these `##` headings, in this order:

1. `## Quickstart`: MUST. A `bash` code block containing exactly `docker compose up`, then how to open the app.
2. `## What works and what is mocked`: MUST. A table with each step and its status: **Working**, or **MOCKED** / **STUBBED**.
3. `## Architecture`: SHOULD. 3–6 sentences and a link to `ARCHITECTURE.md`.
4. `## Models and free resources`: MUST. The open-weight model (e.g. `qwen3:8b` via Ollama) and how to run without paying.
5. `## Cost per run`: MUST. A dollar figure, e.g. `About $0.00 per run (local model, ~40k tokens)`.
6. `## Demo video`: SHOULD. A YouTube, Vimeo, Loom or Google Drive link (3 minutes at most).
7. `## What our system will NOT do`: SHOULD. Our explicit limits (see the ground rules above).
8. `## How the project stays alive after the hackathon`: SHOULD. Maintainers, roadmap, community and funding.

Keep the README focused and put the important facts near the top: long files may be read only in part. Move long material to `docs/`.

## ARCHITECTURE.md

Use these sections:

1. `## Overview`: a paragraph and a diagram.
2. `## Phases`: one `###` per phase, giving its agents, tools, method and output. Cover every Core step in detail.
3. `## Gates`: what each gate checks, its outcomes (go / repeat / pivot / stop), and when the system recommends STOP on weak evidence.
4. `## Sale to cash`: payment triggers delivery, a refund revokes access, idempotency prevents double delivery, and reconciliation matches orders, payments, fees and payouts.
5. `## Data flow`
6. `## Built vs. stubbed`
7. `## Roadmap`

Diagrams must be text: Mermaid (a `mermaid` code block) or ASCII. Images and PDFs are not read. Put the key content first and deeper detail in `docs/`.

## decision_log.json

The code appends one entry for every agent action, and the log of the demo run is committed. Every entry has all five required keys; use `null` or `[]` when one doesn't apply:

```json
[
  {"timestamp": "2026-11-17T09:01:00Z", "agent": "researcher", "action": "find_opportunities", "sources": ["https://www.reddit.com/r/smallbusiness/"], "model": "qwen3:8b", "cost": 0, "approved_by": null},
  {"timestamp": "2026-11-17T09:03:00Z", "agent": "gate", "action": "evidence_gate", "sources": [], "model": null, "cost": 0, "approved_by": null, "outcome": "stop"}
]
```

What the keys hold:
- `action`: a string naming what the agent did.
- `sources`: a list of URLs.
- `model`: a string, or `null` for steps without AI.
- `cost`: a number in USD (`0` for local models).
- `approved_by`: `"founder"` for gated actions, otherwise `null`.

Keep the file small: commit the demo run's log, not every run.

## outputs/

- Use text formats only (`.md`, `.json`, `.csv`, `.txt`, `.html`), and keep each file small.
- Name files `phase<N>_step<M>_<short-name>.<ext>`, and gate decisions `phase<N>_gate_<short-name>.<ext>`. Examples: `outputs/phase1_step1_opportunities.md`, `outputs/phase1_gate_decision.md`.
- Every market claim cites a source URL or is labelled `ASSUMPTION`.
- Include at least one gate decision. With a weak idea, show the system recommending **stop**.
- Payment and delivery test runs go in `outputs/payment_test_log.md`.

## tests/

Put a few smoke tests in `tests/`, with standard names (`test_*.py`, `*.test.ts`). They cover the pipeline steps, the gate, and that nothing goes out without founder approval.

## Keep the repository readable

- Everything that matters is text. Images, PDFs, videos and archives are not read: diagrams go in Mermaid or ASCII, and the demo video is a link.
- Put the important part of every long file first.
- Keep generated code, build output, datasets and dependencies out of git (`.gitignore`).

## Before every push

- [ ] On the default branch; no secrets committed; `.env.example` has placeholders only
- [ ] README has all eight headings; Quickstart shows `docker compose up`; Cost per run has a `$` figure
- [ ] `LICENSE` (OSI-approved, full text) and `docker-compose.yml` at the root
- [ ] `decision_log.json`: every entry has `action`, `sources`, `model`, `cost`, `approved_by`
- [ ] `outputs/` named by phase and step, including a gate decision; claims sourced or labelled `ASSUMPTION`
- [ ] `tests/` has smoke tests, and they pass
- [ ] `ARCHITECTURE.md` covers all six phases, gates and STOP, and sale to cash, with text diagrams
- [ ] Every mock is labelled
