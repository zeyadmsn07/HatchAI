"""PROTOCOL TESTS for the LLM client — NOT model verification.

A tiny OpenAI-compatible stub server (standard library only) plays the model. These tests prove
the client's real HTTP path: request format, timeout, retry limit, schema validation, labelled
fallback, mode labels, and that LLM output can never change evidence scores or gate decisions.
They say nothing about the quality of any real model; see scripts/verify_llm.py for that.
"""
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import db
import llm_gateway as g
import orchestrator
from agents import builder
from agents.intake import parse_brief
from models import SpecText
from tests.test_builder import CANVAS, CRITIQUE

MODEL = "qwen3:0.6b"


class Stub:
    """OpenAI-compatible stub. `script` is a queue of chat behaviours:
    ("json", obj) | ("content", str) | ("status", code) | ("sleep", seconds, obj) | ("raw", bytes)."""

    def __init__(self, models=(MODEL,)):
        self.models = list(models)
        self.script = []
        self.requests = []
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, code, obj):
                raw = json.dumps(obj).encode()
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except OSError:
                    pass   # client gave up (timeout test) — expected

            def do_GET(self):
                stub.requests.append(("GET", self.path, None))
                if self.path == "/v1/models":
                    return self._json(200, {"object": "list", "data": [{"id": m, "object": "model"} for m in stub.models]})
                self._json(404, {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                stub.requests.append(("POST", self.path, body))
                step = stub.script.pop(0) if stub.script else ("content", "")
                kind = step[0]
                if kind == "status":
                    return self._json(step[1], {"error": "stub error"})
                if kind == "sleep":
                    time.sleep(step[1])
                    step = ("json", step[2])
                    kind = "json"
                if kind == "raw":
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(step[1])))
                    self.end_headers()
                    self.wfile.write(step[1])
                    return
                content = json.dumps(step[1]) if kind == "json" else step[1]
                self._json(200, {"id": "x", "object": "chat.completion", "model": body.get("model"),
                                 "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                                              "finish_reason": "stop"}],
                                 "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/v1"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def chats(self):
        return [r for r in self.requests if r[0] == "POST"]


@pytest.fixture
def stub(monkeypatch):
    s = Stub()
    monkeypatch.setenv("HATCHAI_NO_LLM", "0")
    monkeypatch.setenv("HATCHAI_LLM_BASE_URL", s.url)
    monkeypatch.setenv("HATCHAI_LLM_MODEL", MODEL)
    monkeypatch.setenv("HATCHAI_LLM_TIMEOUT", "0.5")
    monkeypatch.setenv("HATCHAI_LLM_RETRIES", "1")
    g.reset_probe_cache()
    yield s
    s.srv.shutdown()
    g.reset_probe_cache()


GOOD = {"product_name": "Calc Cards", "tagline": "Flashcards that schedule your STEM reviews."}


# --- client protocol ---------------------------------------------------------

def test_request_format_and_live_result(stub):
    stub.script = [("json", GOOD)]
    res = g.complete_json("sys prompt", "user prompt", SpecText, temperature=0.3, max_tokens=99)
    assert res.mode == g.LLM_LIVE and res.model == MODEL and res.value.product_name == "Calc Cards"
    assert res.attempts == 1 and res.tokens == 15
    method, path, body = stub.chats()[0]
    assert (method, path) == ("POST", "/v1/chat/completions")
    assert body["model"] == MODEL and body["stream"] is False and body["max_tokens"] == 99
    assert body["response_format"] == {"type": "json_object"} and body["temperature"] == 0.3
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert "sys prompt" in body["messages"][0]["content"] and "JSON schema" in body["messages"][0]["content"]
    assert ("GET", "/v1/models", None) in stub.requests


def test_timeout_triggers_retries_then_labelled_fallback(stub):
    stub.script = [("sleep", 10.0, GOOD), ("sleep", 10.0, GOOD)]   # server would take 20 s in total
    g.probe()
    t0 = time.time()
    res = g.complete_json("s", "u", SpecText)
    assert res.mode == g.LLM_FALLBACK and res.value is None and "timeout" in res.error
    assert res.attempts == 2 and len(stub.chats()) == 2          # 1 try + HATCHAI_LLM_RETRIES=1
    assert time.time() - t0 < 6.0                                # 0.5 s timeouts, not the 20 s of sleeping


def test_retry_recovers_after_server_error(stub):
    stub.script = [("status", 500), ("json", GOOD)]
    res = g.complete_json("s", "u", SpecText)
    assert res.live and res.attempts == 2


def test_retry_limit_is_respected(stub, monkeypatch):
    monkeypatch.setenv("HATCHAI_LLM_RETRIES", "2")
    stub.script = [("content", "nope")] * 5
    res = g.complete_json("s", "u", SpecText)
    assert res.mode == g.LLM_FALLBACK and res.attempts == 3 and len(stub.chats()) == 3


@pytest.mark.parametrize("bad", [
    ("content", "this is not json"),
    ("content", ""),
    ("json", {"wrong": "fields"}),
    ("json", {"product_name": 5}),
    ("raw", b"<html>not an API</html>"),
    ("content", "[1, 2, 3]"),
], ids=["prose", "empty", "schema-missing", "schema-type", "non-json-http", "json-array"])
def test_malformed_responses_fall_back_and_never_crash(stub, bad):
    stub.script = [bad, bad]
    res = g.complete_json("s", "u", SpecText)
    assert res.mode == g.LLM_FALLBACK and res.value is None and res.error


def test_think_tags_and_code_fences_are_stripped(stub):
    stub.script = [("content", "<think>hmm</think>\n```json\n" + json.dumps(GOOD) + "\n```")]
    assert g.complete_json("s", "u", SpecText).live


def test_model_not_served_or_no_endpoint_or_disabled(stub, monkeypatch):
    monkeypatch.setenv("HATCHAI_LLM_MODEL", "llama3.2:1b")
    g.reset_probe_cache()
    res = g.complete_json("s", "u", SpecText)
    assert res.mode == g.LLM_FALLBACK and "not served" in res.error and not stub.chats()

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead = s.getsockname()[1]
    monkeypatch.setenv("HATCHAI_LLM_BASE_URL", f"http://127.0.0.1:{dead}/v1")
    g.reset_probe_cache()
    assert g.complete_json("s", "u", SpecText).mode == g.LLM_FALLBACK

    monkeypatch.setenv("HATCHAI_NO_LLM", "1")
    n = len(stub.requests)
    assert g.complete_json("s", "u", SpecText).mode == g.LLM_DISABLED and len(stub.requests) == n


def test_closed_weight_model_is_refused_without_a_request(stub, monkeypatch):
    monkeypatch.setenv("HATCHAI_LLM_MODEL", "gpt-4o")
    g.reset_probe_cache()
    res = g.complete_json("s", "u", SpecText)
    assert res.mode == g.LLM_FALLBACK and "open-weight" in res.error and not stub.requests


# --- bounded builder tasks --------------------------------------------------------

FLASH = "AI flashcard and spaced-repetition tool for university students in Egypt"


def test_spec_text_task_is_applied_and_labelled_live(stub):
    stub.script = [("json", GOOD)]
    r = builder.run("p-spec", parse_brief(FLASH), CANVAS, CRITIQUE)
    assert r["spec"].product_name == "Calc Cards" and r["tests"]["ok"]
    tasks = {t["task"]: t for t in r["llm_tasks"]}
    assert tasks["spec_text"]["mode"] == g.LLM_LIVE and tasks["spec_text"]["applied"]
    assert tasks["template_suggestion"]["mode"].startswith("not_needed")    # LLM not consulted
    assert len(stub.chats()) == 1
    log = [e for e in db.get_log_entries("p-spec") if e["action"] == "llm_spec_text"]
    assert log[0]["model"] == MODEL and log[0]["outcome"].startswith("LLM_LIVE")


def test_unacceptable_spec_text_is_rejected_by_code(stub):
    stub.script = [("json", {"product_name": "Rich Cards", "tagline": "Guaranteed income from studying!"})]
    r = builder.run("p-reject", parse_brief(FLASH), CANVAS, CRITIQUE)
    t = [t for t in r["llm_tasks"] if t["task"] == "spec_text"][0]
    assert t["mode"] == g.LLM_FALLBACK and "rejected by code" in t["error"] and not t["applied"]
    assert r["spec"].product_name == "Egypt Recall"                  # deterministic text kept
    entry = [e for e in db.get_log_entries("p-reject") if e["action"] == "llm_spec_text"][0]
    assert entry["model"] is None                                    # fallback never shown as model output


def test_template_suggestion_can_only_top_up_with_grounded_synonyms(stub):
    idea = "Daily routine log for night-shift nurses in Kenya"
    det = builder.select_template(idea)
    assert det["archetype"] is None and det["scores"]["habit_tracker"] == 1     # 'routine' only
    stub.script = [("json", {"template": "habit_tracker", "synonyms": [
        {"phrase": "log", "keyword": "track"},
        {"phrase": "diary", "keyword": "journal"},          # not in the idea -> ignored
        {"phrase": "nurses", "keyword": "streak"}]}),       # second credit -> capped
        ("json", GOOD)]
    r = builder.run("p-syn", parse_brief(idea), CANVAS, CRITIQUE)
    t = r["llm_tasks"][0]
    assert t["mode"] == g.LLM_LIVE and t["accepted"] == ["'log' -> track (habit_tracker)"] and t["changed_selection"]
    assert r["spec"].archetype == "habit_tracker" and r["archetype_scores"]["habit_tracker"] == 2
    assert r["tests"]["ok"]


def test_template_suggestion_cannot_rescue_an_unrelated_idea(stub):
    idea = "AI resume feedback tool for job seekers in Egypt"
    stub.script = [("json", {"template": "course", "synonyms": [{"phrase": "feedback", "keyword": "lesson"},
                                                                {"phrase": "resume", "keyword": "course"}]})]
    r = builder.run("p-unrel", parse_brief(idea), CANVAS, CRITIQUE)
    assert r["supported"] is False and r["files"] == 0                 # no deterministic match -> no credit
    t = r["llm_tasks"][0]
    assert t["mode"] == g.LLM_LIVE and t["accepted"] == [] and not t["changed_selection"]
    from gates import evaluate_gate_3
    assert evaluate_gate_3(r).outcome.value == "stop"


def test_bad_suggestion_falls_back_to_deterministic_selection(stub):
    stub.script = [("content", "habit tracker, definitely"), ("content", "still prose")]
    r = builder.run("p-badsug", parse_brief("Mood journal for teenagers"), CANVAS, CRITIQUE)
    t = r["llm_tasks"][0]
    assert t["mode"] == g.LLM_FALLBACK and r["supported"] is False


# --- run-level labels; the LLM never changes evidence, scores or gates ---------------

def _signature(rid):
    return orchestrator._gate_signature(orchestrator._counters(rid)["history"])


def test_live_run_labels_and_identical_decisions(stub, strong_collector, monkeypatch):
    stub.script = [("json", GOOD)]
    run = orchestrator.run_sync(orchestrator.DEMO_BRIEF_STRONG, "p-live", auto=True)
    assert run["status"] == "completed"
    out = orchestrator.out_dir("p-live")
    assert "LLM mode: LLM_LIVE at run start (model qwen3:0.6b" in (out / "phase1_step1_intake.md").read_text(encoding="utf-8")
    spec = (out / "phase3_step1_mvp-spec.md").read_text(encoding="utf-8")
    assert f"LLM mode: LLM_LIVE (model {MODEL}; template_suggestion" not in spec   # suggestion not consulted
    assert f"LLM mode: LLM_LIVE (model {MODEL}; spec_text=LLM_LIVE)" in spec and "Calc Cards" in spec
    start = [e for e in db.get_log_entries("p-live") if e["action"] == "llm_mode_at_start"][0]
    assert start["model"] == MODEL and start["outcome"].startswith("LLM_LIVE")

    monkeypatch.setenv("HATCHAI_NO_LLM", "1")
    off = orchestrator.run_sync(orchestrator.DEMO_BRIEF_STRONG, "p-off", auto=True)
    assert off["status"] == "completed" and _signature("p-live") == _signature("p-off")
    f_live = orchestrator._load("p-live", "findings", orchestrator.ResearchFindings)
    f_off = orchestrator._load("p-off", "findings", orchestrator.ResearchFindings)
    assert f_live.model_dump() == f_off.model_dump()
    assert "LLM mode: LLM_DISABLED" in (orchestrator.out_dir("p-off") / "phase2_step1_critique.md").read_text(encoding="utf-8")


def test_unreachable_endpoint_run_is_labelled_fallback(strong_collector, monkeypatch):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead = s.getsockname()[1]
    monkeypatch.setenv("HATCHAI_NO_LLM", "0")
    monkeypatch.setenv("HATCHAI_LLM_BASE_URL", f"http://127.0.0.1:{dead}/v1")
    g.reset_probe_cache()
    run = orchestrator.run_sync(orchestrator.DEMO_BRIEF_STRONG, "p-fb", auto=True)
    g.reset_probe_cache()
    assert run["status"] == "completed"
    spec = (orchestrator.out_dir("p-fb") / "phase3_step1_mvp-spec.md").read_text(encoding="utf-8")
    assert "LLM mode: LLM_UNAVAILABLE_FALLBACK (deterministic fallback used; spec_text=LLM_UNAVAILABLE_FALLBACK)" in spec
    assert all(e["model"] is None for e in db.get_log_entries("p-fb", limit=500))


def test_replay_is_llm_disabled_even_with_an_endpoint(stub, monkeypatch):
    from tests.test_replay import _no_network
    _no_network(monkeypatch)
    n = len(stub.requests)
    orchestrator.replay(orchestrator.DEMO_SNAPSHOT, run_id="p-replay")
    assert len(stub.requests) == n                                    # zero LLM traffic
    text = (orchestrator.out_dir("p-replay") / "phase3_step1_mvp-spec.md").read_text(encoding="utf-8")
    assert "LLM mode: LLM_DISABLED" in text


# --- scripts/verify_llm.py -------------------------------------------------------

def _verify(monkeypatch, capsys, low=False):
    import importlib.util
    spec = importlib.util.spec_from_file_location("verify_llm", orchestrator.ROOT / "scripts" / "verify_llm.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "resources", lambda: {"disk_free_gb": {"repo drive (D:)": 0.5 if low else 50.0},
                                                   "mem_free_gb": 8.0})
    code = mod.main()
    return code, capsys.readouterr().out


def test_verify_script_reports_not_verified_without_endpoint(monkeypatch, capsys):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead = s.getsockname()[1]
    monkeypatch.setenv("HATCHAI_NO_LLM", "0")
    monkeypatch.setenv("HATCHAI_LLM_BASE_URL", f"http://127.0.0.1:{dead}/v1")
    g.reset_probe_cache()
    code, out = _verify(monkeypatch, capsys)
    assert code == 1 and "NOT VERIFIED: no local LLM endpoint" in out


def test_verify_script_skips_heavy_work_on_low_resources(stub, monkeypatch, capsys):
    code, out = _verify(monkeypatch, capsys, low=True)
    assert code == 2 and "attempting nothing heavy" in out.lower() and not stub.chats()


def test_verify_script_round_trip_against_stub(stub, monkeypatch, capsys):
    stub.script = [("json", {"answer": "ok", "number": 7})]
    code, out = _verify(monkeypatch, capsys)
    assert code == 0 and "VERIFIED" in out and MODEL in out          # protocol only: the 'model' is a stub
