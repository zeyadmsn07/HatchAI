"""Advisor agent: turns scores and lists into an insight memo for the founder after Gates 1, 2 and 3.

The memo answers five questions, from the stored results of the run:
  1. What does the verified evidence say the pain is?
  2. Does the current plan (the idea at Gates 1-2, the MVP's features at Gate 3) address that pain?
  3. What is the weakest assumption, and which evidence-specific risks follow from the audit?
  4. What is the cheapest test this week?
  5. What would change the recommendation? (code-computed counterfactuals: remove one cited source,
     re-run the same gate function, report whether the outcome changes)
plus evidence-based angles (a pain competitors ignore, an underserved place or language, a price gap).

Rules:
  * Rule-based text is always produced (and is the only text in replays): deterministic.
  * When a local open-weight model is live, it may add a short summary written ONLY from the
    verified quotes and their source keys.
  * Every sentence of every section passes `insight_check`: it cites a source key of a verified
    claim, or says ASSUMPTION. Other sentences are removed and counted.
  * The memo is advisory. It never changes E, V, a gate outcome or the pivot the gate proposes.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

import callbacks
import evidence
import gates
import insight_check
import llm_gateway
from models import Critique, FounderBrief, ResearchFindings

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "prompts" / "advisor.md"


_LABEL = {"demand": "Demand evidence", "pricing": "Pricing evidence", "competitors": "Competitor evidence",
          "local_constraints": "Local-constraint evidence", "channels": "Channel evidence"}


_CONSEQUENCE = {"demand": "whether anyone has the problem", "pricing": "the price users would accept",
                "competitors": "how crowded the market is", "local_constraints": "whether users can access and pay",
                "channels": "the plan to reach users"}


class AdvisorText(BaseModel):
    sentences: List[str] = Field(default_factory=list, min_length=1, max_length=6)


def _q(text: str, n: int = 160) -> str:
    """A quote fragment that cannot be split into several sentences by the citation checker."""
    t = re.sub(r"[.!?]+\s+", "; ", text.strip()).rstrip(".!? ")
    t = t.replace("“", "'").replace("”", "'").replace('"', "'")
    return (t[:n].rsplit(" ", 1)[0] + "…") if len(t) > n else t


def _keys(ks) -> str:
    ks = sorted(set(ks), key=lambda k: int(k[1:]) if k[1:].isdigit() else 0)
    return ", ".join(ks)


def _known(v: str) -> str:
    return "" if not v or str(v).upper().startswith(("UNKNOWN", "ASSUMPTION")) else str(v)


def _verified(findings: ResearchFindings, cat: str | None = None):
    return [c for c in findings.claims if c.verified and not c.is_assumption and (cat is None or c.category == cat)]


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _pain_section(findings, pains) -> list[str]:
    if pains:
        return [f"{p['key']} (verified demand) names this pain: '{_q(p['phrase'])}'." for p in pains]
    demand = _verified(findings, "demand")
    if demand:
        c = demand[0]
        return [f"{c.source_keys[0]} is the verified demand evidence, but it describes the market, not a pain: "
                f"'{_q(c.quote)}'.",
                "ASSUMPTION: the pain this product targets has not been observed in any source; it is inferred "
                "from the idea itself."]
    return ["ASSUMPTION: no verified source describes demand or a pain for this brief, so the problem is "
            "the founder's hypothesis, not a finding."]


def _plan_section(gate_id, brief, pains, features) -> tuple[list[str], dict | None]:
    from agents.builder import coverage
    if not pains:
        return ["ASSUMPTION: there is no verified pain to check the plan against, so product-problem fit is "
                "untested; the demand test in Phase 6 is the first real check."], None
    if gate_id >= 3 and features:
        cov = coverage(features, pains)
        lines = [f"{r['key']}: the MVP addresses '{_q(r['phrase'], 90)}' with {', '.join(r['features'])}."
                 if r["features"] else
                 (f"{r['key']}: no MVP feature solves '{_q(r['phrase'], 90)}' yet, so the builder added a pain "
                  "question to the waitlist; the demand test collects visitors' own words about it."
                  if r.get("measured_by") else
                  f"{r['key']}: no MVP feature addresses '{_q(r['phrase'], 90)}'.")
                 for r in cov["rows"]]
        lines.append(f"The MVP covers {cov['covered']} of {cov['total']} verified pains "
                     f"({_keys(r['key'] for r in cov['rows'])}).")
        return lines, cov
    cov = coverage([{"name": "the idea as written", "description": brief.idea}], pains)
    lines = [f"{r['key']}: the idea as written {'mentions' if r['features'] else 'does not mention'} "
             f"'{_q(r['phrase'], 90)}'." for r in cov["rows"]]
    lines.append("ASSUMPTION: the MVP's features are chosen in Phase 3; this check reruns on them there.")
    return lines, cov


def _risks(findings, audit, critique) -> tuple[list[str], list[str], str]:
    """(weakest-assumption lines, evidence-specific risk lines, weakest category)."""
    verified_cats = gates.verified_categories(findings)
    rows = audit["rows"]
    weak, risks = [], []
    demand = _verified(findings, "demand")
    weakest = ""
    if not demand:
        weakest = "demand"
        weak.append("ASSUMPTION: demand is the weakest link: no verified source shows that the target users "
                    "have this problem.")
    elif len({c.source_keys[0] for c in demand}) == 1:
        weakest = "demand"
        weak.append(f"Demand rests on a single source ({demand[0].source_keys[0]}); one misread page would "
                    "remove the only evidence that anyone has the problem.")
    for cat in evidence.CATEGORIES:
        if cat not in verified_cats and not (cat == "demand" and not demand):
            weak.append(f"ASSUMPTION: {cat.replace('_', ' ')} has no verified source.")
            weakest = weakest or cat
    order = ("demand", "pricing", "competitors", "local_constraints", "channels")
    only_weak = sorted(audit["summary"]["categories_only_vendor_or_stale"], key=order.index)
    for cat in only_weak:
        ks = [r["key"] for r in rows if r["category"] == cat]
        weak.append(f"{_LABEL[cat]} rests only on vendor or stale sources ({_keys(ks)}), so "
                    f"{_CONSEQUENCE[cat]} is untested today; confirm it with one independent, current source.")
        weakest = weakest or cat

    vendor_pricing = [r["key"] for r in rows if r["category"] == "pricing" and r["credibility"].startswith("vendor")]
    if vendor_pricing:
        risks.append(f"Pricing rests on vendor sources ({_keys(vendor_pricing)}), which quote their own prices. "
                     "ASSUMPTION (kill criterion): fewer than 3 of 10 target users say they would pay the entry "
                     "price. ASSUMPTION (cheapest test): ask them before building any paid tier.")
    elif "pricing" not in verified_cats:
        risks.append("ASSUMPTION: no verified price exists, so the price is an estimate. ASSUMPTION (kill "
                     "criterion): fewer than 3 of 10 target users accept the entry price when asked directly.")
    for r in rows:
        if r["freshness"] == "stale":
            risks.append(f"{r['key']} ({r['category'].replace('_', ' ')}) dates from {r['published']}, so "
                         "the plan built on it is untested today. ASSUMPTION (kill criterion): the channel or "
                         "fact cannot be confirmed by one current source.")
    snip = [r["key"] for r in rows if r["origin"] == "search-snippet"]
    if rows and len(snip) / len(rows) >= 0.5:
        risks.append(f"{int(100 * len(snip) / len(rows))}% of verified quotes ({_keys(snip)}) come from search "
                     "snippets, not the page. ASSUMPTION (cheapest test): open those pages and confirm the "
                     "sentence is there in context.")
    if critique:
        for k in critique.riskiest_assumptions[:2]:
            risks.append(f"ASSUMPTION (from the Phase 2 critique): {k.assumption}; kill criterion: {k.kill_criterion.rstrip('. ')}.")
    return weak, risks, weakest


def _cheapest_test(weakest, findings, brief, demand_test) -> list[str]:
    user = _known(brief.target_user) or "target users"
    geo = _known(brief.geography)
    chans = sorted({c.source_keys[0] for c in _verified(findings, "channels")})
    where = f" in {geo}" if geo else ""
    if weakest == "pricing":
        lines = [f"ASSUMPTION (proposed test, USD 0, 1 week): show the entry price next to a free core on the "
                 f"MVP landing page and ask 10 {user}{where} whether they would pay it; record yes / no / why."]
    else:
        lines = [f"ASSUMPTION (proposed test, USD 0, 1 week): interview 5 {user}{where} about the last time "
                 "they had this problem and what they did about it, then share the MVP landing page and count "
                 "consented waitlist sign-ups."]
    if chans:
        lines.append(f"Channels with verified evidence to start from: {_keys(chans)}.")
    if demand_test:
        lines.append(f"ASSUMPTION: the pre-registered rule then decides in Phase 6 (at least "
                     f"{demand_test.min_unique_visitors} unique visitors; persevere at ≥ "
                     f"{int(demand_test.go_signup_rate * 100)}% sign-ups, stop below "
                     f"{int(demand_test.stop_signup_rate * 100)}%).")
    return lines


def _without(findings: ResearchFindings, key: str) -> ResearchFindings:
    f = findings.model_copy(deep=True)
    f.claims = [c for c in f.claims if key not in c.source_keys]
    return f


def _counterfactuals(gate_id, gate, findings, brief, critique, round_no, pivots) -> tuple[list[str], list[str]]:
    """Remove each cited source in turn and re-run the same gate function. Code-computed."""
    if gate_id not in (1, 2):
        return [], ["ASSUMPTION: Gate 3 depends only on the generated tests passing and the server booting; "
                    "evidence cannot change it, but a failing test would turn it into REPEAT."]
    cited = sorted(insight_check.verified_keys(findings.claims), key=lambda k: int(k[1:]))
    table, flips = [], []
    for k in cited:
        f2 = _without(findings, k)
        if gate_id == 1:
            g2 = gates.evaluate_gate_1(f2, brief, round_no=round_no, pivots_used=pivots)
        else:
            v2, b2 = gates.compute_viability(f2, brief, critique.riskiest_assumptions)
            c2 = critique.model_copy(update={"viability_score": v2, "viability_breakdown": b2})
            g2 = gates.evaluate_gate_2(f2, c2, round_no=round_no, pivots_used=pivots)
        e2 = gates.compute_evidence_score(f2)
        changed = g2.outcome != gate.outcome
        table.append(f"| {k} | {e2} | {g2.outcome.value.upper()} | {'**changes**' if changed else 'same'} |")
        if changed:
            flips.append(f"Removing {k} alone would change Gate {gate_id} from {gate.outcome.value.upper()} to "
                         f"{g2.outcome.value.upper()} (E {gate.evidence_score} → {e2}).")
    if cited and not flips:
        flips.append(f"No single source ({_keys(cited)}) changes the Gate {gate_id} outcome when removed, so the "
                     "recommendation does not hinge on one page.")
    return table, flips


def _angles(findings, brief, pains) -> list[str]:
    """Evidence-based angles, ranked by the Strategist (same list the gate's pivot is drawn from)."""
    from agents.strategist import candidates
    out = [c["angle"] for c in candidates(findings, brief)]
    if not out:
        out.append("ASSUMPTION: the verified evidence shows no gap that competitors leave open; no angle "
                   "is proposed rather than inventing one.")
    return out


def _llm_summary(findings, sections_text: str, max_rounds: int = 2) -> tuple[list[str], list[str], dict]:
    """Generate -> verify -> revise. The model drafts sentences from the verified quotes only; the
    code citation check (`insight_check`) rejects any sentence without a verified source key or an
    ASSUMPTION label; rejected sentences go back to the model once, with the reason, for a rewrite.
    Only sentences that pass the code check are ever shown."""
    claims = _verified(findings)
    if not claims:
        return [], [], {"mode": "not_needed (no verified claims)", "model": None}
    allowed = insight_check.verified_keys(claims)
    quotes = "\n".join(f"[{c.source_keys[0]}] ({c.category}) {_q(c.quote, 160)}" for c in claims[:8])
    system = PROMPT.read_text(encoding="utf-8")
    user = (f"/no_think\nVerified quotes:\n{quotes}\n\nAnalysis computed by code:\n{sections_text[:600]}\n\n"
            "Write 3 to 5 sentences.")
    kept: list[str] = []
    removed: list[str] = []
    meta = {"mode": llm_gateway.LLM_FALLBACK, "model": None, "tokens": 0, "rounds": 0}
    for rnd in range(max_rounds):
        res = llm_gateway.complete_json(system, user, AdvisorText, temperature=0.2, max_tokens=700)
        if not res.live:
            if rnd == 0:
                return [], [], {"mode": res.mode, "model": None, "error": res.error}
            break
        meta.update(mode=res.mode, model=res.model, tokens=meta["tokens"] + (res.tokens or 0), rounds=rnd + 1)
        k, r = insight_check.check_lines(res.value.sentences[:6], allowed)
        kept += [x for x in k if x not in kept]
        if not r or len(kept) >= 5:
            break
        removed = r
        user = (f"/no_think\nVerified quotes:\n{quotes}\n\nThese sentences were REJECTED by the citation "
                "checker because they cite no verified source key in square brackets and are not labelled "
                "ASSUMPTION:\n" + "\n".join(f"- {x}" for x in r[:6]) +
                f"\n\nAllowed source keys: {', '.join(sorted(allowed))}. Rewrite each rejected sentence so it "
                "states one specific point and ends with the key of the quote it rests on, e.g. [S3], or "
                "starts with 'ASSUMPTION:'. Do not add new facts.")
    return kept[:6], removed, meta


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(run_id: str, gate_id: int, gate, brief: FounderBrief, findings: ResearchFindings,
        critique: Critique | None = None, features: list | None = None, demand_test=None,
        round_no: int = 1, pivots: int = 0) -> dict:
    allowed = insight_check.verified_keys(findings.claims)
    audit = evidence.quality_report(findings.sources, findings.claims)
    pains = evidence.pain_signals(findings.claims, brief.idea, _known(brief.target_user))

    pain = _pain_section(findings, pains)
    plan, cov = _plan_section(gate_id, brief, pains, features or [])
    weak, risks, weakest = _risks(findings, audit, critique)
    test = _cheapest_test(weakest, findings, brief, demand_test)
    table, flips = _counterfactuals(gate_id, gate, findings, brief, critique, round_no, pivots)
    angles = _angles(findings, brief, pains)

    removed_all: list[str] = []
    checked = {}
    for name, lines in (("pain", pain), ("plan", plan), ("weak", weak), ("risks", risks), ("test", test),
                        ("flips", flips), ("angles", angles)):
        kept, removed = insight_check.check_lines(lines, allowed)
        checked[name], removed_all = kept, removed_all + removed

    # Opt-in (HATCHAI_ADVISOR_LLM=1) so a default run keeps its documented budget of 2 small LLM calls.
    use_llm = findings.evidence_mode != "replay" and os.environ.get("HATCHAI_ADVISOR_LLM", "0") == "1"
    llm_kept, llm_removed, llm = ([], [], {"mode": llm_gateway.LLM_DISABLED, "model": None}) if not use_llm else \
        _llm_summary(findings, "\n".join(checked["pain"] + checked["plan"] + checked["weak"] + checked["flips"]))
    removed_all += llm_removed

    def bullets(xs):
        return "\n".join(f"- {x}" for x in xs) or "- (nothing passed the citation check)"

    llm_block = (f"*Written by `{llm['model']}` from the verified quotes only; every sentence re-checked by "
                 f"code, rejected ones sent back once for a rewrite ({llm.get('rounds', 1)} round(s); "
                 f"{len(llm_kept)} kept, {len(llm_removed)} still removed).*\n\n{bullets(llm_kept)}"
                 if llm.get("model") else
                 (f"Not produced (LLM mode: {llm['mode']}; enable with HATCHAI_ADVISOR_LLM=1 and a local or free-tier "
                  "open-weight model). "
                  "The sections above are rule-based and complete without it."))
    gate_word = gate.outcome.value.upper()
    memo = f"""# Phase {gate_id} — Advisor memo (after Gate {gate_id}: {gate_word})

> **Advisory only.** This memo interprets the stored results; it never changes E, V, the gate outcome or
> the pivot the gate proposes. Every sentence cites a verified source key (S…) or says ASSUMPTION;
> **{len(removed_all)}** sentence(s) failed that check and were removed.

## 1. What the evidence says the pain is

{bullets(checked['pain'])}

## 2. Does the current plan address it?

{bullets(checked['plan'])}

## 3. Weakest assumption

{bullets(checked['weak'][:1])}

Other gaps:

{bullets(checked['weak'][1:]) if checked['weak'][1:] else '- none'}

### Evidence-specific risks (from the evidence audit)

{bullets(checked['risks']) if checked['risks'] else '- none found by the audit'}

## 4. Cheapest test this week

{bullets(checked['test'])}

## 5. What would change the recommendation

{bullets(checked['flips'])}
{'' if not table else chr(10) + "Each row re-runs the Gate " + str(gate_id) + " function with one cited source removed (computed by code):" + chr(10) + chr(10) + "| Source removed | E without it | Gate outcome | vs. now |" + chr(10) + "|---|---|---|---|" + chr(10) + chr(10).join(table)}

## Evidence-based angles

{bullets(checked['angles'])}

## Model-written summary (optional)

{llm_block}
"""
    srcs = sorted({s.url for s in findings.sources if s.key in allowed})
    callbacks.log(run_id, "advisor", f"advisor_memo_gate_{gate_id}", sources=srcs, model=llm.get("model"),
                  cost=0, phase=gate_id, tokens=llm.get("tokens"),
                  outcome=(f"pains={len(pains)}; coverage={cov['covered']}/{cov['total']}; " if cov else
                           f"pains={len(pains)}; ") + f"removed_sentences={len(removed_all)}")
    return {"memo": memo, "pains": pains, "coverage": cov, "removed": removed_all, "llm": llm,
            "flips": [f for f in flips if f.startswith("Removing")]}
