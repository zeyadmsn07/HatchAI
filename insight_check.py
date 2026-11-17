"""Citation discipline for advisory text (the Advisor memo).

Every sentence must either cite a source key of a VERIFIED claim, e.g. (S6), or say ASSUMPTION.
Sentences that do neither are removed, and the removal is counted and reported. Nothing here can
change E, V or a gate outcome.
"""
from __future__ import annotations

import re

_KEY = re.compile(r"\bS(\d+)\b")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")


def verified_keys(claims) -> set[str]:
    return {k for c in claims if c.verified and not c.is_assumption for k in c.source_keys}


def sentence_ok(sentence: str, allowed: set[str]) -> bool:
    if "ASSUMPTION" in sentence:
        return True
    keys = {f"S{n}" for n in _KEY.findall(sentence)}
    return bool(keys) and keys <= allowed


def check_text(text: str, allowed: set[str]) -> tuple[str, list[str]]:
    """Filter one paragraph or bullet. Returns (kept text, removed sentences)."""
    kept, removed = [], []
    for s in _SENT.split(text.strip()):
        if not s.strip():
            continue
        (kept if sentence_ok(s, allowed) else removed).append(s.strip())
    return " ".join(kept), removed


def check_lines(lines: list[str], allowed: set[str]) -> tuple[list[str], list[str]]:
    out, removed = [], []
    for line in lines:
        kept, rem = check_text(line, allowed)
        removed += rem
        if kept:
            out.append(kept)
    return out, removed
