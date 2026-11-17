"""Intake agent — normalises the founder brief (deterministic, no LLM).

The parser decides which fields the founder actually supplied; any field the founder
did not supply is marked UNKNOWN and listed in `unknown_fields`. No LLM is used here,
so nothing can turn a guess into a fact.
"""
from __future__ import annotations

import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import callbacks
import evidence
from models import FounderBrief

TRACKED = ("target_user", "geography", "skills", "budget_usd", "hours_per_week", "values")


def parse_brief(raw: str) -> FounderBrief:
    text = raw.strip()
    low = text.lower()
    fields: dict = {}

    def form(label):
        m = re.search(rf"(?im)^\s*{label}\s*:\s*(.+)$", text)
        return m.group(1).strip() if m and m.group(1).strip() else None

    first = re.split(r"\n|(?<=[.!?])\s", text, maxsplit=1)[0]
    first = re.sub(r"(?i)^\s*(i|we)\s+(want|plan|would like)\s+to\s+(build|create|make|launch|start)\s+", "", first)
    first = first[:1].upper() + first[1:]
    fields["idea"] = first.strip()[:240] or text[:240]

    # target user
    tu = form("target user")
    if not tu and not re.search(r"(don't|do not|dont) know who", low):
        m = re.search(r"\bfor ((?:[a-z0-9\-]+ ){0,5}(?:students|teachers|founders|freelancers|developers|"
                      r"designers|parents|owners|businesses|creators|tutors|clinics|shops|learners|"
                      r"professionals|employees|managers|writers|artists|musicians|coaches|families|"
                      r"marketers|researchers|engineers|nurses|drivers|users|people|teams|agencies))",
                      low)
        tu = m.group(1).strip() if m else None
    if tu:
        fields["target_user"] = tu

    geo = form("geography")
    if not geo:
        c = evidence.detect_country(text)
        geo = c[0] if c else None
    if geo:
        fields["geography"] = geo

    sk = form("skills")
    if not sk:
        m = re.search(r"i have ([a-z0-9 ,/&\-]+?) skills", low)
        sk = m.group(1).strip() if m and "no particular" not in m.group(0) else None
    if sk and not re.search(r"\b(no|none)\b", sk.lower()):
        fields["skills"] = sk

    m = re.search(r"budget\s*:?\s*(?:usd|\$|egp|eur|£|€)?\s*\$?(\d[\d,]*(?:\.\d+)?)", low) or \
        re.search(r"(?:usd|\$)\s?(\d[\d,]*)", low) or re.search(r"(\d[\d,]*)\s?(?:usd|dollars)", low)
    if m:
        fields["budget_usd"] = float(m.group(1).replace(",", ""))
    elif re.search(r"\bno budget\b", low):
        fields["budget_usd"] = 0.0

    m = form("hours per week") or (re.search(r"(\d+(?:\.\d+)?)\s*(?:hours|hrs|h)\s*(?:per|a|/)\s*week", low) or [None, None])[1]
    if m:
        fields["hours_per_week"] = float(re.sub(r"[^\d.]", "", str(m)) or 0)

    va = form("values")
    if not va:
        m = re.search(r"i value ([^.\n]+)", low)
        va = m.group(1).strip() if m else None
    if va:
        fields["values"] = va

    langs = [l for l in ("arabic", "english", "french", "spanish", "hindi", "urdu") if l in low]
    if langs:
        fields["language"] = "/".join(l.title() for l in langs)

    unknown = [f for f in TRACKED if f not in fields]
    brief = FounderBrief(**fields)
    brief.unknown_fields = unknown
    for f in unknown:
        if f in ("budget_usd", "hours_per_week"):
            brief.assumptions.append(f"{f} not stated — default {getattr(brief, f)} used (ASSUMPTION)")
        else:
            setattr(brief, f, f"UNKNOWN (not stated by founder)")
            brief.assumptions.append(f"{f} not stated by founder")
    return brief


def run(run_id: str, raw_text: str) -> FounderBrief:
    brief = parse_brief(raw_text)
    callbacks.log(run_id=run_id, agent="intake", action="normalize_brief", sources=[],
                  model=None, cost=0, phase=1)
    return brief
