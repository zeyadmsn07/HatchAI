"""Shared fixtures: isolated DB/output dirs, no network, no LLM, and a fake evidence ledger.

Network-free by design: `evidence.collect` is replaced by `fake_collect`, which returns
fixture passages (clearly fake example.org URLs) so gate behaviour is deterministic.
"""
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models import Source

STRONG = {
    "demand": [("https://forum.example.org/a", "Students say spaced repetition flashcards help them; a survey found 61% struggle to revise STEM material.")],
    "competitors": [("https://review.example.com/b", "Compare the best flashcard apps for students: Anki and Quizlet lead the market.")],
    "pricing": [("https://pricing.example.net/c", "Premium flashcard apps cost $4.99/month for students on the subscription plan.")],
    "local_constraints": [("https://data.example.int/d", "GDP per capita (current US$) for Egypt, Arab Rep. in 2025: 3,085.8.")],
    "channels": [("https://news.example.io/e", "University students discover study flashcard tools through Facebook groups and TikTok community posts.")],
}


def make_sources(spec: dict) -> list[Source]:
    out = []
    for cat, items in spec.items():
        for url, passage in items:
            key = f"S{len(out) + 1}"
            out.append(Source(key=key, url=url, title=f"Fixture {key}", domain=url.split("/")[2],
                              fetch_time="2026-11-17T00:00:00+00:00", text_hash="fixture", passages=[passage],
                              collector="worldbank" if cat == "local_constraints" else ("hn" if cat == "demand" else "web:fixture"),
                              category=cat))
    return out


class FakeCollector:
    """Returns a different fixture ledger per research round: rounds[round_no-1]."""

    def __init__(self, rounds):
        self.rounds = rounds
        self.calls = []

    def __call__(self, idea, target_user, geography, round_no=1, existing=None):
        self.calls.append((idea, round_no))
        spec = self.rounds[min(round_no, len(self.rounds)) - 1]
        existing = list(existing or [])
        new = make_sources(spec)
        for s in new:
            s.key = f"S{len(existing) + 1}"
            existing.append(s)
        return existing, {s.key: s.category for s in existing}


REPO = Path(__file__).resolve().parent.parent


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Temp dirs go to <repo>/.pytest_tmp (relative to the repo root, whatever the working directory),
    unless --basetemp is given explicitly."""
    if not config.option.basetemp:
        config.option.basetemp = str(REPO / ".pytest_tmp")
# Committed artifacts that no test may create, change or delete.
PROTECTED = ("outputs", "decision_log.json", "evidence_snapshots")


def repo_artifact_hashes() -> dict[str, str]:
    """SHA-256 of every file under the protected paths (missing paths recorded as such)."""
    out = {}
    for rel in PROTECTED:
        p = REPO / rel
        files = sorted(f for f in p.rglob("*") if f.is_file()) if p.is_dir() else ([p] if p.exists() else [])
        if not files:
            out[rel] = "<missing>"
        for f in files:
            out[f.relative_to(REPO).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


@pytest.fixture(scope="session", autouse=True)
def committed_artifacts_untouched():
    """Fails the session if any test changed outputs/, decision_log.json or evidence_snapshots/."""
    before = repo_artifact_hashes()
    yield
    after = repo_artifact_hashes()
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    assert not changed, f"tests modified committed artifacts: {changed}"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("HATCHAI_OFFLINE", "1")
    monkeypatch.setenv("HATCHAI_NO_LLM", "1")
    # The synthetic fixture evidence below was written for the v1 relevance rule, and these tests check
    # pipeline mechanics, not relevance. Live runs default to scoring v2 outside tests; v2 behaviour is
    # tested explicitly in tests/test_scoring_v2.py (which sets HATCHAI_SCORING=v2 itself).
    monkeypatch.setenv("HATCHAI_SCORING", "v1")
    import db
    import llm_gateway
    import orchestrator
    import payments
    from agents import builder
    monkeypatch.setattr(orchestrator, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(orchestrator, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(builder, "GENERATED", tmp_path / "generated")
    llm_gateway.reset_probe_cache()          # no LLM probe result leaks between tests
    db.init_db()
    payments.init_payments()
    yield tmp_path
    llm_gateway.reset_probe_cache()


@pytest.fixture
def strong_collector(monkeypatch):
    import evidence
    fc = FakeCollector([STRONG])
    monkeypatch.setattr(evidence, "collect", fc)
    return fc
