"""Open-weight model policy, and the Phase 6 decision rule never inventing results."""
import pytest

import llm_gateway
from agents import operate
from models import FounderBrief


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


def test_preregistered_rule():
    assert operate.decide(0, 0)[0] == "INSUFFICIENT_DATA"
    assert operate.decide(40, 300)[0] == "PERSEVERE"
    assert operate.decide(15, 300)[0] == "PIVOT"
    assert operate.decide(5, 300)[0] == "STOP"


def test_operate_reports_real_zero_not_synthetic(tmp_path):
    m = operate.read_mvp_metrics(tmp_path)
    assert m["signups"] == 0 and "not yet run" in m["source"]
