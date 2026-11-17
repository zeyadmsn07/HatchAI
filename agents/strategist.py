"""Strategist agent: turns the verified evidence into ranked, evidence-backed pivot candidates.

Before this agent, a PIVOT restated the idea ("Narrow the idea to <user> in <place>: <idea>").
Now every candidate comes from a gap that the verified evidence itself shows:

  pain_gap      a verified demand source names a pain that none of the verified competitor sources mention
  localisation  the competitor sources never mention the founder's place/language, while another source does
  price_gap     the median competitor price is above a local affordability cap computed from World Bank GDP
  institutions  a verified source mentions institutions (schools, employers...) that serve the target user

Each candidate cites its source keys. The ranking is deterministic:
  score = base weight of the gap type + number of distinct verified sources behind it
so a gap that two sources point at beats one that rests on one page. No LLM is involved, and the
gate (code) still decides whether to pivot at all; this agent only proposes *where*.
"""
from __future__ import annotations

import re
import statistics

import evidence
from models import FounderBrief, ResearchFindings

_INSTITUTION = re.compile(r"\b(universit(y|ies) administrat\w*|institution\w*|schools?|enterprise\w*|"
                          r"employers?|b2b)\b", re.I)
_WEIGHT = {"pain_gap": 4, "localisation": 3, "price_gap": 3, "institutions": 1}


def _known(v: str) -> str:
    return "" if not v or str(v).upper().startswith(("UNKNOWN", "ASSUMPTION")) else str(v)


def short_idea(idea: str) -> str:
    """'An AI flashcard tool for students in Egypt, ...' -> 'AI flashcard tool'"""
    core = re.split(r"\s+(?:for|in|that|which|to help)\s+|[,.:]", idea, maxsplit=1)[0]
    core = re.sub(r"(?i)^(an?|the)\s+", "", core.strip())
    return core[:80] or idea[:80]


def _q(text: str, n: int = 80) -> str:
    t = re.sub(r"[.!?]+\s+", "; ", text.strip()).rstrip(".!? ").replace('"', "'")
    return (t[:n].rsplit(" ", 1)[0] + "…") if len(t) > n else t


def _keys(ks) -> str:
    return ", ".join(sorted(set(ks), key=lambda k: int(k[1:]) if k[1:].isdigit() else 0))


def _verified(findings: ResearchFindings, cat: str | None = None):
    return [c for c in findings.claims if c.verified and not c.is_assumption and (cat is None or c.category == cat)]


def candidates(findings: ResearchFindings, brief: FounderBrief) -> list[dict]:
    """Ranked pivot candidates: [{"kind", "idea", "angle", "keys", "score"}], best first."""
    from agents.commercial import price_evidence
    target = _known(brief.target_user) or "a named user group"
    geo = _known(brief.geography)
    where = f" in {geo}" if geo else ""
    short = short_idea(brief.idea)
    pains = evidence.pain_signals(findings.claims, brief.idea, _known(brief.target_user))
    comp = _verified(findings, "competitors")
    comp_keys = sorted({c.source_keys[0] for c in comp})
    by_key = {s.key: s for s in findings.sources}
    comp_text = " ".join(" ".join(by_key[k].passages) for k in comp_keys if k in by_key).lower()
    out: list[dict] = []

    for p in pains:
        if comp_keys and not any(t[:6] in comp_text for t in p["terms"]):
            phrase = _q(p["phrase"], 70)
            out.append({"kind": "pain_gap", "keys": [p["key"], *comp_keys],
                        "idea": f"{short} for {target}{where}, built around one pain: {phrase}",
                        "angle": f"{p['key']} names '{phrase}', and none of the verified competitor sources "
                                 f"({_keys(comp_keys)}) mention it: build the product around that pain."})

    bt = evidence.brief_terms(brief.idea, brief.target_user, brief.geography, brief.language)
    local = [t for t in bt["local"] if t]
    if comp_keys and local:
        missing = [t for t in local if t not in comp_text]
        loc_keys = sorted({c.source_keys[0] for c in _verified(findings)
                           if any(t in c.quote.lower() for t in missing)} - set(comp_keys))
        if missing and loc_keys:
            names = " or ".join(m.title() for m in missing)
            geo_low = geo.lower()
            lang = [m.title() for m in missing if m not in geo_low]
            focus = (f"{' and '.join(lang)}-first" if lang else
                     f"with content and pricing made for {geo}" if geo else f"localised for {names}")
            out.append({"kind": "localisation", "keys": loc_keys + comp_keys,
                        "idea": f"{short} for {target}{where}, {focus}",
                        "angle": f"The verified competitor sources ({_keys(comp_keys)}) never mention {names}, "
                                 f"while {_keys(loc_keys)} {'does' if len(loc_keys) == 1 else 'do'}: a localised "
                                 "version is an underserved segment."})

    prices, gdp = price_evidence(findings)
    url_key = {s.url: s.key for s in findings.sources}
    pk = sorted({url_key[u] for _, u in prices if u in url_key})
    if prices and gdp and gdp[2] in url_key:
        med = round(statistics.median(v for v, _ in prices), 2)
        cap = round(gdp[0] / 12 * 0.01, 2)
        if med > cap:
            out.append({"kind": "price_gap", "keys": pk + [url_key[gdp[2]]],
                        "idea": f"{short} for {target}{where} with a free core and a paid tier under USD {cap}/month",
                        "angle": f"Competitor prices in {_keys(pk)} have a median of USD {med}/month, against a "
                                 f"local affordability cap of USD {cap}/month from {url_key[gdp[2]]} "
                                 "(ASSUMPTION: cap = 1% of monthly GDP per capita): a free core with a low-cost "
                                 "tier is the price gap."})

    inst = sorted({c.source_keys[0] for c in _verified(findings) if _INSTITUTION.search(c.quote)})
    if inst:
        out.append({"kind": "institutions", "keys": inst,
                    "idea": f"{short} sold to the institutions that serve {target}{where}",
                    "angle": f"{_keys(inst)} {'mentions' if len(inst) == 1 else 'mention'} institutions, so "
                             "selling to them is an evidence-based option."})

    for c in out:
        c["keys"] = sorted(set(c["keys"]), key=lambda k: int(k[1:]) if k[1:].isdigit() else 0)
        c["score"] = _WEIGHT[c["kind"]] + len(c["keys"])
    # stable: equal scores keep the order above (pain > localisation > price > institutions)
    return sorted(out, key=lambda c: -c["score"])


def legacy_angles(brief: FounderBrief, idea: str, verified: set[str]) -> list[str]:
    """The pre-Strategist rule-based angles. Kept only so evidence snapshots captured before the
    Strategist existed replay to the same pivot text (their pivot round was collected for it)."""
    target = _known(brief.target_user) or "a narrower, named user group"
    geo = _known(brief.geography) or "one specific country"
    angles = [f"Narrow the idea to {target} in {geo}: {idea[:90]}"]
    if "competitors" in verified:
        angles.append(f"ASSUMPTION: differentiate from the incumbents in the competitor evidence via "
                      f"{brief.language} localisation for {target}")
    angles.append(f"ASSUMPTION: B2B version — sell to institutions that serve {target}")
    return angles
