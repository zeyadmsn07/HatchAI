"""Tests never read or write the committed outputs/, decision_log.json, evidence_snapshots/ or hatchai.db.

The session-wide guard in conftest.py (committed_artifacts_untouched) hashes those paths before and
after the whole run; these tests check that every write target is redirected while a test runs.
"""
import os

import orchestrator
from agents import builder
from tests.conftest import REPO, repo_artifact_hashes


def test_write_targets_point_to_temp_dirs(tmp_path):
    assert orchestrator.OUTPUTS == tmp_path / "outputs"
    assert orchestrator.RUNS == tmp_path / "runs"
    assert builder.GENERATED == tmp_path / "generated"
    assert os.environ["DB_PATH"] == str(tmp_path / "test.db")
    # pytest temp lives in the gitignored .pytest_tmp/ (repo drive), never inside a protected path
    assert (REPO / ".pytest_tmp") in tmp_path.parents
    assert not any((REPO / p) in tmp_path.parents for p in ("outputs", "evidence_snapshots", "runs"))
    assert os.environ["HATCHAI_NO_LLM"] == "1" and os.environ["HATCHAI_OFFLINE"] == "1"


def test_a_full_pipeline_run_leaves_committed_artifacts_untouched(strong_collector):
    before = repo_artifact_hashes()
    run = orchestrator.run_sync(orchestrator.DEMO_BRIEF_STRONG, "demo-strong", auto=True)   # a demo run id
    assert run["status"] == "completed"
    assert (orchestrator.OUTPUTS / "phase6_step1_operate-memo.md").exists()                 # wrote to temp
    assert repo_artifact_hashes() == before
