"""Evidence replay: no network, deterministic, clearly labelled, faithful to the captured snapshot."""
import json
import socket

import httpx
import pytest

import db
import evidence
import orchestrator
from tests.conftest import STRONG, FakeCollector

BRIEF = orchestrator.DEMO_BRIEF_STRONG


def _no_network(monkeypatch):
    """Any attempt to reach a non-loopback host fails the test."""
    def boom(*a, **k):
        raise AssertionError("network access attempted during replay")
    for name in ("search_web", "search_hn", "search_wikipedia", "worldbank_indicators", "collect"):
        monkeypatch.setattr(evidence, name, boom)
    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.setattr(httpx, "post", boom)
    real_connect = socket.socket.connect

    def guarded(self, addr):
        host = addr[0] if isinstance(addr, tuple) else addr
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise AssertionError(f"network connection to {host} during replay")
        return real_connect(self, addr)
    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.fixture
def repeat_snapshot(monkeypatch, tmp_path):
    """Capture a REPEAT -> GO run from fixture evidence (thin round 1, full round 2)."""
    fc = FakeCollector([{"demand": STRONG["demand"]}, STRONG])
    monkeypatch.setattr(evidence, "collect", fc)
    path = tmp_path / "snap.json"
    snap = orchestrator.capture(BRIEF, path, run_id="cap-1", label="fixture repeat")
    monkeypatch.undo()
    return path, snap


def test_capture_records_sources_claims_and_gates(repeat_snapshot):
    path, snap = repeat_snapshot
    assert snap["snapshot_version"] == 1 and snap["brief"] == BRIEF
    assert [r["round"] for r in snap["rounds"]] == [1, 2]
    src = snap["rounds"][0]["sources"][0]
    assert {"key", "url", "title", "domain", "fetch_time", "text_hash", "passages", "collector", "category"} <= set(src)
    assert snap["rounds"][1]["verified_claims_at_capture"]
    assert [h["outcome"] for h in snap["gate_outcomes_at_capture"]][:2] == ["repeat", "go"]
    assert json.loads(path.read_text(encoding="utf-8")) == snap


def test_replay_makes_no_network_requests_and_matches_capture(repeat_snapshot, monkeypatch):
    path, snap = repeat_snapshot
    _no_network(monkeypatch)
    res = orchestrator.replay(path, run_id="rep-1")
    assert res["match"] is True
    assert res["run"]["status"] == snap["final_status_at_capture"] == "completed"
    assert [h["outcome"] for h in res["replayed"]] == [h["outcome"] for h in snap["gate_outcomes_at_capture"]]


def test_replay_is_deterministic(repeat_snapshot, monkeypatch):
    path, _ = repeat_snapshot
    _no_network(monkeypatch)
    outs = []
    for rid in ("rep-a", "rep-b"):
        res = orchestrator.replay(path, run_id=rid)
        d = orchestrator.out_dir(rid)
        files = {n: (d / n).read_text(encoding="utf-8") for n in (
            "phase1_step2_research-findings.md", "phase1_step3_sources.json", "phase1_gate_decision.md",
            "phase2_step1_critique.md", "phase2_gate_decision.md", "phase4_step1_pricing.md")}
        outs.append((orchestrator._gate_signature(res["replayed"]), files))
    assert outs[0] == outs[1]


def test_replay_preserves_original_source_data(repeat_snapshot, monkeypatch):
    path, snap = repeat_snapshot
    _no_network(monkeypatch)
    orchestrator.replay(path, run_id="rep-src")
    replayed = json.loads((orchestrator.out_dir("rep-src") / "phase1_step3_sources.json").read_text(encoding="utf-8"))
    captured = [s for r in snap["rounds"] for s in r["sources"]]
    assert replayed == captured                 # URLs, passages, original fetch times, hashes unchanged
    findings = orchestrator._load("rep-src", "findings", orchestrator.ResearchFindings)
    verified_now = sorted((c.category, c.quote) for c in findings.claims if c.verified)
    verified_then = sorted((c["category"], c["quote"]) for c in snap["rounds"][-1]["verified_claims_at_capture"])
    assert verified_now == verified_then        # re-verification reproduces the captured verification


def test_replay_is_labelled_in_outputs_and_log(repeat_snapshot, monkeypatch):
    path, snap = repeat_snapshot
    _no_network(monkeypatch)
    orchestrator.replay(path, run_id="rep-lbl")
    d = orchestrator.out_dir("rep-lbl")
    assert "**Evidence mode: REPLAY**" in (d / "phase1_step2_research-findings.md").read_text(encoding="utf-8")
    assert "**Evidence mode: REPLAY**" in (d / "phase1_gate_decision.md").read_text(encoding="utf-8")
    check = (d / "phase1_step4_evidence-replay-check.md").read_text(encoding="utf-8")
    assert "Nothing was fetched" in check and "MATCH" in check and snap["captured_at"] in check
    actions = [e["action"] for e in db.get_log_entries("rep-lbl", limit=500)]
    assert "replay_evidence_round_1" in actions and "replay_evidence_round_2" in actions
    assert not any(a.startswith("collect_evidence") for a in actions)
    replay_entries = [e for e in db.get_log_entries("rep-lbl", limit=500) if e["action"].startswith("replay_evidence")]
    assert all("REPLAY of snapshot" in e["outcome"] and "no new collection" in e["outcome"] for e in replay_entries)


def test_missing_round_fails_closed_instead_of_searching(repeat_snapshot, monkeypatch, tmp_path):
    path, snap = repeat_snapshot
    snap = dict(snap, rounds=snap["rounds"][:1])            # drop round 2
    short = tmp_path / "short.json"
    short.write_text(json.dumps(snap), encoding="utf-8")
    _no_network(monkeypatch)
    res = orchestrator.replay(short, run_id="rep-miss")
    assert res["run"]["status"] == "failed" and "no captured evidence for round 2" in res["run"]["error"]
    assert res["match"] is False


def test_committed_snapshot_replays_to_repeat_then_go(monkeypatch):
    """The snapshot in the repository (captured from a live run) reproduces REPEAT -> GO offline."""
    _no_network(monkeypatch)
    res = orchestrator.replay(orchestrator.DEMO_SNAPSHOT, run_id="rep-committed")
    assert res["match"] is True
    outcomes = [h["outcome"] for h in res["replayed"]]
    assert outcomes[:2] == ["repeat", "go"]
