"""The committed demo is reproducible: all scenarios replay from snapshots with zero network access."""
import json

import pytest

import db
import evidence
import orchestrator
from tests.conftest import STRONG, FakeCollector
from tests.test_replay import _no_network

SNAPSHOT_FILES = sorted(orchestrator.SNAPSHOTS.glob("*_scenario.json"))

# Files that legitimately differ between two runs: random order ids, entitlement tokens and payment
# timestamps (payment logs); a random server port and wall-clock duration (MVP test reports).
ALLOWED_TO_DIFFER = ("payment_test_log", "phase3_step3_mvp-test-report")


def test_three_committed_snapshots_exist():
    assert [p.name for p in SNAPSHOT_FILES] == ["repeat_scenario.json", "strong_scenario.json",
                                                "strong_v2_scenario.json", "weak_scenario.json"]
    for name in ("strong_scenario.json", "weak_scenario.json", "strong_v2_scenario.json"):
        snap = json.loads((orchestrator.SNAPSHOTS / name).read_text(encoding="utf-8"))
        assert snap["capture_metadata"]["code_state"]["commit"]          # newer captures carry metadata


@pytest.mark.parametrize("path", SNAPSHOT_FILES, ids=lambda p: p.stem)
def test_each_snapshot_replays_to_its_captured_outcomes_offline(path, monkeypatch):
    _no_network(monkeypatch)
    res = orchestrator.replay(path, run_id=f"snap-{path.stem}")
    snap = json.loads(path.read_text(encoding="utf-8"))
    assert res["match"] is True
    assert res["run"]["status"] == snap["final_status_at_capture"]
    assert orchestrator._gate_signature(res["replayed"]) == orchestrator._gate_signature(snap["gate_outcomes_at_capture"])


def _snapshot_outputs():
    d = orchestrator.OUTPUTS
    return {p.name: p.read_text(encoding="utf-8") for p in d.iterdir() if p.is_file()}


def test_two_default_demo_runs_are_identical(monkeypatch, tmp_path):
    _no_network(monkeypatch)
    r1 = orchestrator.run_demo(log_path=tmp_path / "log1.json")
    out1 = _snapshot_outputs()
    r2 = orchestrator.run_demo(log_path=tmp_path / "log2.json")
    out2 = _snapshot_outputs()

    v1_runs = {"demo-strong": "completed", "demo-weak": "stopped", "demo-replay": "completed"}
    assert {k: r1[k]["status"] for k in v1_runs} == v1_runs
    assert r1["demo-headline"]["status"] == "completed"                 # live v2 capture, replayed under v2
    assert set(r1) == set(v1_runs) | {f"{k}-v2" for k in v1_runs} | {"demo-headline"}
    for rid in r1:
        if rid in v1_runs or rid == "demo-headline":      # captured under v1, replayed under v1: must reproduce the capture exactly
            assert r1[rid]["match"] is True and r2[rid]["match"] is True
        else:                   # replayed under v2: a labelled scoring-version difference, not a match
            assert r1[rid]["scoring_difference"] is True and r1[rid]["match"] is False
        assert orchestrator._gate_signature(r1[rid]["history"]) == orchestrator._gate_signature(r2[rid]["history"])

    assert sorted(out1) == sorted(out2)
    compared = [n for n in out1 if not n.startswith(ALLOWED_TO_DIFFER)]
    assert len(compared) >= 41
    for n in compared:
        assert out1[n] == out2[n], f"{n} differs between two default demo runs"
    for n, text in out1.items():                        # every text output names its evidence mode
        if n.endswith((".md", ".txt")):
            assert "vidence mode: **REPLAY" in text or "vidence mode: REPLAY" in text, n

    strip = lambda log: [{k: v for k, v in e.items() if k != "timestamp"} for e in log]
    l1 = json.loads((tmp_path / "log1.json").read_text(encoding="utf-8"))
    l2 = json.loads((tmp_path / "log2.json").read_text(encoding="utf-8"))
    assert strip(l1) == strip(l2)
    assert not any(e["action"].startswith("collect_evidence") for e in l1)


def test_demo_live_selects_live_research(monkeypatch, tmp_path):
    fc = FakeCollector([STRONG])
    monkeypatch.setattr(evidence, "collect", fc)
    res = orchestrator.run_demo(live=True, log_path=tmp_path / "log.json")
    assert {idea[:20] for idea, _ in fc.calls} >= {"An AI-powered flashc", "An app that sells ge"}
    for rid in ("demo-strong", "demo-weak"):
        f = orchestrator._load(rid, "findings", orchestrator.ResearchFindings)
        assert f.evidence_mode == "live" and res[rid]["match"] is None
    entries = db.get_log_entries("demo-strong", limit=500)
    assert any(e["action"] == "collect_evidence_round_1" and e["outcome"] == "LIVE collection in this run"
               for e in entries)
    assert "Evidence mode: live" in (orchestrator.OUTPUTS / "phase2_step1_critique.md").read_text(encoding="utf-8")
    # the REPEAT -> GO scenario is always a replay
    assert orchestrator._load("demo-replay", "findings", orchestrator.ResearchFindings).evidence_mode == "replay"


# --- the default demo never silently falls back to live research -------------------------

def _temp_scenarios(tmp_path, monkeypatch, hide=None, corrupt=None):
    """Point the demo at temp COPIES of the committed snapshots (the originals are only read)."""
    import shutil
    d = tmp_path / "snaps"
    d.mkdir()
    scenarios = {}
    for rid, (brief, snap) in orchestrator.DEMO_SCENARIOS.items():
        copy = d / snap.name
        shutil.copyfile(snap, copy)
        if snap.name == hide:
            copy.unlink()
        if snap.name == corrupt:
            copy.write_text("{ not json", encoding="utf-8")
        scenarios[rid] = (brief, copy)
    monkeypatch.setattr(orchestrator, "DEMO_SCENARIOS", scenarios)
    return d


@pytest.mark.parametrize("name", ["strong_scenario.json", "weak_scenario.json", "repeat_scenario.json"])
def test_default_demo_fails_clearly_when_a_snapshot_is_missing(name, tmp_path, monkeypatch, capsys):
    d = _temp_scenarios(tmp_path, monkeypatch, hide=name)
    code = orchestrator.main(["demo"])
    err = capsys.readouterr().err
    assert code == 2
    assert f"snapshot missing: {d / name}; run `python orchestrator.py demo --live` for live research" in err
    assert db.get_run("demo-strong") is None and db.get_run("demo-weak") is None     # nothing ran, nothing reset
    assert not orchestrator.OUTPUTS.exists() or not any(orchestrator.OUTPUTS.iterdir())


def test_default_demo_fails_clearly_when_a_snapshot_is_unreadable(tmp_path, monkeypatch, capsys):
    d = _temp_scenarios(tmp_path, monkeypatch, corrupt="weak_scenario.json")
    assert orchestrator.main(["demo"]) == 2
    assert f"snapshot unreadable: {d / 'weak_scenario.json'}" in capsys.readouterr().err


def test_live_demo_still_needs_the_repeat_snapshot(tmp_path, monkeypatch, capsys):
    _temp_scenarios(tmp_path, monkeypatch, hide="repeat_scenario.json")
    assert orchestrator.main(["demo", "--live"]) == 2      # the REPEAT -> GO scenario is always a replay
    assert "snapshot missing" in capsys.readouterr().err
