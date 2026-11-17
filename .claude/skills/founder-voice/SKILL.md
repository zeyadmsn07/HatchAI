---
name: founder-voice
description: Rewrite HatchAI's founder-facing text (Advisor memo templates, Strategist pivot angles, Phase 2 critique risks, Lean Canvas and MVP feature traces, and the prompts in prompts/) so it reads like a sharp human startup advisor, with every point tied to evidence. Use when editing agents/advisor.py, agents/strategist.py, agents/validator.py, agents/builder.py traces, prompts/advisor.md or prompts/builder.md, or when a generated output in outputs/ reads generic, circular or templated.
---

# Founder voice

HatchAI's founder-facing sentences are produced by code templates and, optionally, by an open-weight
model. This skill is for **editing those templates and prompts**. It does not change gates, scores,
thresholds or approval logic. Never touch `gates.py` thresholds, `config/gates.yaml` or `approval.py`
while applying it.

## Rules for every founder-facing sentence

1. **One specific point, tied to evidence.** Cite the source key of a verified claim (`S6`) or start
   with `ASSUMPTION:`. `insight_check.py` deletes any Advisor sentence that does neither, so a template
   that forgets the key silently loses its line.
2. **Conclusion → reason → next action.** "Demand rests on one page (S12), so one misread removes it;
   interview 5 students this week (USD 0) before building more."
3. **Never restate the idea as the problem.** "students lack an adequate flashcard tool" is circular.
   Name the pain the quote names, or say the pain is an ASSUMPTION to be confirmed by interviews.
4. **Banned phrasing:** "leverage", "unlock", "game-changer", "synergy", "robust solution",
   "B2B version", "narrow the idea", "in today's world", "lack an adequate".
5. **Never promise income or success. Never invent numbers, sources, competitors or users.**
   Numbers come from code (E, V, prices, GDP caps) or from a quoted source.
6. Plain verbs, short sentences, concrete nouns from the founder's own brief (their user, their
   country, their language).
7. Keep fragments inside one sentence when they are quotes: use the `_q()` helpers so a quote with
   a full stop does not split into an uncited sentence.

## Before → after (from this repository's outputs)

| Where | Before | After |
|---|---|---|
| MVP feature trace (`agents/builder.py`) | `university students lack an adequate Narrow the idea to university students.` | `Verified pain S6: 'the burden of card preparation …'`, or `ASSUMPTION (job to be done): university students forget material between study sessions and cram before exams` |
| Phase 2 critique (`agents/validator.py`) | `Target users will pay a recurring price` | `university students will pay a recurring price in the USD 4.99–8/month range that S3, S4 quote; those are competitor or vendor prices, not what this segment has agreed to pay` |
| Gate pivot (`agents/strategist.py`) | `Narrow the idea to university students in Egypt: An AI-powered flashca…` | `AI-powered flashcard and spaced-repetition study tool for university students in Egypt, built around one pain: the burden of card preparation …` with *why*: `S6 names '…', and none of the verified competitor sources (S2, S3) mention it` |
| Evidence angle | `ASSUMPTION: B2B version — sell to institutions that serve university students` | `S9 mentions institutions, so selling to them is an evidence-based option.` (or no angle at all when no source mentions them) |
| Advisor risk line | `Channels rests only on…` (category label, no point) | `Channel evidence rests only on vendor or stale sources (S8), so the plan to reach users is untested today.` |

## How to apply

1. Find the template or prompt text that produced the sentence (`grep -rn "<phrase>" agents prompts`).
2. Rewrite it with the rules above. Keep every `ASSUMPTION` label and every source key placeholder.
3. Run `python -m pytest`, then `python orchestrator.py demo`, and compare the changed file in
   `outputs/` with `git diff outputs/`. Commit the regenerated outputs. Never hand-edit `outputs/`.
