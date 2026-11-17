"""Open-weight model policy, and the Phase 6 decision rule never inventing results."""
import pytest

import llm_gateway
from agents import operate
from models import DemandTest, FounderBrief


def test_only_open_weight_models_are_accepted(monkeypatch):
    for ok in ("qwen3:8b", "llama-3.3-70b-versatile", "gemma3:4b", "mistral:7b", "gpt-oss:20b"):
        assert llm_gateway.is_open_weight(ok), ok
    for closed in ("gpt-4o", "gemini-1.5-flash", "claude-3-5-sonnet"):
        assert not llm_gateway.is_open_weight(closed), closed
    monkeypatch.setenv("OLLAMA_MODEL", "gemini-1.5-flash")
    with pytest.raises(llm_gateway.ClosedWeightModelError):
        llm_gateway.ollama_model()


def test_no_model_means_no_fabricated_answer():
    assert llm_gateway.active_model_label() is None
    assert llm_gateway.call_llm("sys", "user", FounderBrief) is None


DT = DemandTest(channel="c", metric="m", threshold="t", duration_days=14, cost_usd=0)


def test_preregistered_rule():
    assert operate.decide(0, 0, DT)[0] == "INSUFFICIENT_DATA"
    assert operate.decide(40, 300, DT)[0] == "PERSEVERE"
    assert operate.decide(15, 300, DT)[0] == "PIVOT"
    assert operate.decide(5, 300, DT)[0] == "STOP"


def test_thresholds_come_from_stored_demand_test():
    strict = DT.model_copy(update={"min_unique_visitors": 1000, "go_signup_rate": 0.2, "stop_signup_rate": 0.05})
    assert operate.decide(40, 300, strict)[0] == "INSUFFICIENT_DATA"   # PERSEVERE under the default rule
    assert operate.decide(150, 1000, strict)[0] == "PIVOT"
    assert operate.decide(40, 1000, strict)[0] == "STOP"
    assert "1000" in operate.decide(1, 10, strict)[1]
    assert not hasattr(operate, "MIN_VISITORS")                          # no duplicated constants


def test_operate_reports_zero_when_no_mvp_database(tmp_path):
    m = operate.read_mvp_metrics(tmp_path)
    assert m["real"] == m["test"] == {"visits": 0, "unique_visitors": 0, "signups": 0}
    assert "no MVP database yet" in m["source"]
