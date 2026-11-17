"""Phase 6 measures real stored counts from the generated MVP; TEST traffic is labelled and kept apart."""
import importlib.util
import json

import pytest

import db
import orchestrator
from agents import builder, operate
from agents.intake import parse_brief
from demand_test_traffic import send_test_traffic
from models import DemandTest
from tests.test_builder import CANVAS, CRITIQUE, IDEAS

DT = DemandTest(channel="c", metric="m", threshold="t", duration_days=14, cost_usd=0)


@pytest.fixture
def mvp_dir():
    report = builder.run("t-measure", parse_brief(IDEAS["spaced_repetition"]), CANVAS, CRITIQUE)
    assert report["tests"]["ok"]
    return report["app_dir"]


def _store(app_dir):
    spec = importlib.util.spec_from_file_location("mvp_store_for_test", app_dir / "store.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Store(str(app_dir / "app.db"))


def test_test_traffic_is_counted_persisted_and_labelled(mvp_dir):
    res = send_test_traffic(mvp_dir, visitors=12, signups=3)
    assert res["label"] == "TEST"
    assert res["metrics"]["test"] == {"visits": 12, "unique_visitors": 12, "signups": 3}
    assert res["metrics"]["real"] == {"visits": 0, "unique_visitors": 0, "signups": 0}
    # persisted in the MVP's own app.db: a second server process adds to the same totals
    res2 = send_test_traffic(mvp_dir, visitors=5, signups=1)
    assert res2["metrics"]["test"]["visits"] == 17 and res2["metrics"]["test"]["signups"] == 4
    s = _store(mvp_dir)
    signups = s.events("waitlist")
    visits = s.events("visit")
    s.conn.close()
    assert all(e["traffic"] == "test" and e["email"].endswith("@example.com") for e in signups)
    assert all(e["traffic"] == "test" and e["visitor"].startswith("test-") for e in visits)


def test_traffic_script_rejects_bad_input(mvp_dir, tmp_path):
    with pytest.raises(ValueError):
        send_test_traffic(mvp_dir, visitors=2, signups=5)
    with pytest.raises(FileNotFoundError):
        send_test_traffic(tmp_path, visitors=1, signups=0)


def test_phase6_reads_actual_database_values(mvp_dir):
    s = _store(mvp_dir)       # fixture rows written straight into the MVP database for this test
    for i in range(4):
        s.add_event("visit", None, {"visitor": f"fixture-real-{i}", "traffic": "real", "path": "/"})
    s.add_event("waitlist", None, {"email": "fixture@realdomain.test", "traffic": "real"})
    s.conn.close()
    send_test_traffic(mvp_dir, visitors=6, signups=2)
    m = operate.read_mvp_metrics(mvp_dir)
    assert m["real"] == {"visits": 4, "unique_visitors": 4, "signups": 1}
    assert m["test"] == {"visits": 6, "unique_visitors": 6, "signups": 2}

    small = DT.model_copy(update={"min_unique_visitors": 4})
    memo = operate.run("t-measure", parse_brief(IDEAS["spaced_repetition"]), small, mvp_dir)
    assert "## Decision on real traffic: **PERSEVERE**" in memo          # 1/4 = 25% >= 10%
    assert "TEST traffic — pipeline check, NOT demand" in memo
    assert "| Unique visitors | 6 |" in memo and "excluded from the decision" in memo


def test_insufficient_real_data_is_reported_even_with_lots_of_test_traffic(mvp_dir):
    send_test_traffic(mvp_dir, visitors=310, signups=40)
    memo = operate.run("t-measure", parse_brief(IDEAS["spaced_repetition"]), DT, mvp_dir)
    assert "## Decision on real traffic: **INSUFFICIENT_DATA**" in memo
    assert "0 unique visitors < 300 required" in memo
    assert "Rule applied to TEST data: **PERSEVERE**" in memo


def test_end_to_end_measure_after_completed_run(strong_collector):
    run = orchestrator.run_sync(orchestrator.DEMO_BRIEF_STRONG, "e2e-measure", auto=True)
    assert run["status"] == "completed"
    with pytest.raises(ValueError):
        orchestrator.measure("does-not-exist")
    dt = orchestrator._load("e2e-measure", "demand_test", DemandTest)
    assert (dt.min_unique_visitors, dt.go_signup_rate, dt.stop_signup_rate) == (300, 0.10, 0.03)
    app_dir = orchestrator._load("e2e-measure", "app")["app_dir"]
    send_test_traffic(app_dir, visitors=300, signups=20)
    memo = orchestrator.measure("e2e-measure")
    assert "**INSUFFICIENT_DATA**" in memo and "Rule applied to TEST data: **PIVOT**" in memo   # 20/300 = 6.7%
    written = (orchestrator.out_dir("e2e-measure") / "phase6_step1_operate-memo.md").read_text(encoding="utf-8")
    assert written == memo
    outcomes = [e["outcome"] for e in db.get_log_entries("e2e-measure", limit=500) if e["agent"] == "operate"]
    assert any(o.startswith("insufficient_data (real: 0 visitors") for o in outcomes)
    assert "TEST only: pivot" in outcomes
