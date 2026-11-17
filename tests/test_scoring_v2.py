"""Scoring v2 (brief-specific relevance) vs v1.

SYNTHETIC FIXTURES: the passages below are hand-written test inputs (example.org URLs). They are not
evidence about any market; they exist only to show what each relevance rule counts.
"""
import json

import pytest

import db
import evidence
import orchestrator
from models import Source
from tests.conftest import STRONG, FakeCollector
from tests.test_replay import _no_network

IDEA = "A flashcard app for STEM revision for university students in Egypt"
USER, GEO, LANG = "university students", "Egypt", "Arabic/English"


def _src(key, text, collector="web:fixture", category="demand"):
    return Source(key=key, url=f"https://fixture.example.org/{key}", title=f"SYNTHETIC {key}",
                  domain="fixture.example.org", fetch_time="2026-11-17T00:00:00+00:00", text_hash="x",
                  passages=[text], collector=collector, category=category)


# --- synthetic relevance cases -------------------------------------------------------------

BARELY_RELATED_HN = _src("S1", "Ask HN: Books to learn about Arabic text processing — Hacker News thread with "
                               "2 points and 3 comments, posted 2015-10-24.", collector="hn")
GENERIC_STAT = _src("S2", "The online education market reached 1.5 billion users worldwide, showing strong demand "
                          "for flashcard apps among university students, including in Egypt.")
SPECIFIC = _src("S3", "University students in Egypt say they struggle to revise STEM material and want "
                      "flashcard practice in Arabic before exams.")


def _demand_keys(claims):
    return [c.source_keys[0] for c in claims if c.category == "demand"]


def test_v1_counts_the_barely_related_thread_and_the_generic_statistic_as_demand():
    claims = evidence.extractive_claims([BARELY_RELATED_HN, GENERIC_STAT], "Arabic flashcard app", USER, "v1")
    assert set(_demand_keys(claims)) == {"S1", "S2"}


def test_v2_rejects_barely_related_thread_and_generic_statistic_but_counts_specific_source():
    claims = evidence.extractive_claims([BARELY_RELATED_HN, GENERIC_STAT, SPECIFIC], IDEA, USER, "v2", GEO, LANG)
    assert _demand_keys(claims) == ["S3"]


def test_v2_demand_needs_user_problem_and_local_context():
    no_local = _src("S4", "University students say they struggle to revise STEM material with flashcards.")
    no_user = _src("S5", "In Egypt, revising STEM material with flashcards is a struggle.")
    claims = evidence.extractive_claims([no_local, no_user], IDEA, USER, "v2", GEO, LANG)
    assert _demand_keys(claims) == []


def test_v2_brief_without_user_or_geography_can_never_verify_demand():
    claims = evidence.extractive_claims([SPECIFIC], IDEA, "UNKNOWN (not stated by founder)", "v2",
                                        "UNKNOWN (not stated by founder)", "English")
    assert _demand_keys(claims) == [] and not any(c.category == "local_constraints" for c in claims)


def test_v1_dispatch_is_unchanged():
    srcs = [BARELY_RELATED_HN, GENERIC_STAT, SPECIFIC]
    a = evidence.extractive_claims(srcs, IDEA, USER)                       # default = v1
    b = evidence.extractive_claims_v1(srcs, IDEA, USER)
    assert [c.model_dump() for c in a] == [c.model_dump() for c in b]
    with pytest.raises(ValueError):
        evidence.extractive_claims(srcs, IDEA, USER, "v3")


# --- replaying the committed snapshots -----------------------------------------------------

@pytest.mark.parametrize("name", ["strong_scenario.json", "weak_scenario.json", "repeat_scenario.json"])
def test_v1_replay_still_reproduces_capture_exactly(name, monkeypatch):
    _no_network(monkeypatch)
    res = orchestrator.replay(orchestrator.SNAPSHOTS / name, run_id=f"v1-{name}", scoring="v1")
    assert res["match"] is True and res["scoring_difference"] is False


def test_v2_replay_is_deterministic_offline_and_labelled(monkeypatch):
    _no_network(monkeypatch)
    snap = orchestrator.SNAPSHOTS / "repeat_scenario.json"
    sigs, files = [], []
    for rid in ("v2-a", "v2-b"):
        res = orchestrator.replay(snap, run_id=rid, scoring="v2")
        assert res["scoring_difference"] is True and res["match"] is False
        sigs.append(orchestrator._gate_signature(res["replayed"]))
        d = orchestrator.out_dir(rid)
        files.append({n: (d / n).read_text(encoding="utf-8").replace(rid, "RID")
                      for n in ("phase1_step2_research-findings.md", "phase1_gate_decision.md",
                                "phase1_step4_evidence-replay-check.md")})
    assert sigs[0] == sigs[1] and files[0] == files[1]
    check = files[0]["phase1_step4_evidence-replay-check.md"]
    assert "**Captured under v1:**" in check and "**Replayed under v2:**" in check
    assert "SCORING-VERSION DIFFERENCE" in check
    assert "Scoring version: v2" in files[0]["phase1_step2_research-findings.md"]
    entries = db.get_log_entries("v2-a", limit=500)
    assert entries and all(e["scoring_version"] == "v2" for e in entries)


def test_v2_replay_that_needs_uncaptured_evidence_stops_with_a_reason(monkeypatch):
    _no_network(monkeypatch)
    res = orchestrator.replay(orchestrator.SNAPSHOTS / "strong_scenario.json", run_id="v2-strong", scoring="v2")
    assert res["run"]["status"] == "stopped"
    assert "needs evidence the snapshot does not contain (captured under v1)" in res["run"]["error"]
    assert [h["outcome"] for h in res["replayed"]] == ["repeat"]


def test_cli_replay_scoring_flag(monkeypatch, capsys):
    _no_network(monkeypatch)
    snap = str(orchestrator.SNAPSHOTS / "weak_scenario.json")
    assert orchestrator.main(["replay", snap, "cli-v1", "--scoring", "v1"]) == 0
    assert "gate outcomes match capture: True" in capsys.readouterr().out
    assert orchestrator.main(["replay", snap, "cli-v2", "--scoring", "v2"]) == 0
    out = capsys.readouterr().out
    assert "captured under v1:" in out and "replayed under v2:" in out and "scoring-version difference" in out


# --- new live runs use v2 ------------------------------------------------------------------

def test_new_live_runs_default_to_v2_and_captures_record_it(monkeypatch, tmp_path):
    monkeypatch.delenv("HATCHAI_SCORING", raising=False)
    monkeypatch.setattr(evidence, "collect", FakeCollector([STRONG]))
    snap = orchestrator.capture(orchestrator.DEMO_BRIEF_STRONG, tmp_path / "s.json", run_id="live-v2")
    assert snap["scoring_version"] == "v2"
    f = orchestrator._load("live-v2", "findings", orchestrator.ResearchFindings)
    assert f.scoring_version == "v2"
    assert json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))["scoring_version"] == "v2"
