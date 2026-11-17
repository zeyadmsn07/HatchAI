"""LLM gateway — one small client for a LOCAL, OpenAI-compatible, open-weight model endpoint.

Works with any server that speaks the OpenAI chat-completions protocol: Ollama (`/v1`),
llama.cpp `llama-server`, vLLM, LM Studio. No paid APIs, no hosted services, no API keys.

Configuration (environment):
  HATCHAI_LLM_BASE_URL  base URL(s) ending in /v1, comma-separated   default http://localhost:11434/v1
                        (legacy OLLAMA_BASE_URL is accepted; "/v1" is appended if missing)
  HATCHAI_LLM_MODEL     open-weight model name served there           default qwen3:8b  (legacy OLLAMA_MODEL)
  HATCHAI_LLM_TIMEOUT   seconds per HTTP request                       default 60
  HATCHAI_LLM_RETRIES   extra attempts after a failed/invalid answer   default 1
  HATCHAI_NO_LLM=1      switch the LLM off entirely                    -> LLM_DISABLED

Every call returns an LLMResult with one of three explicit modes:
  LLM_LIVE                  a real model answered and the answer passed schema validation
  LLM_UNAVAILABLE_FALLBACK  enabled, but no endpoint/model, or timeout / HTTP error / empty /
                            malformed / schema-invalid after all retries -> caller uses its
                            deterministic fallback and labels the output as such
  LLM_DISABLED              switched off (HATCHAI_NO_LLM=1; replays and the default demo)

Nothing here can raise into the pipeline: every failure becomes a labelled fallback.
Closed-weight model names are refused (`is_open_weight`).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Generic, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

LLM_LIVE = "LLM_LIVE"
LLM_FALLBACK = "LLM_UNAVAILABLE_FALLBACK"
LLM_DISABLED = "LLM_DISABLED"

OPEN_WEIGHT_FAMILIES = (
    "qwen", "llama", "gemma", "mistral", "mixtral", "phi", "deepseek",
    "gpt-oss", "olmo", "granite", "smollm", "tinyllama",
)
_DEFAULT_MODEL = "qwen3:8b"
_DEFAULT_BASE = "http://localhost:11434/v1"
_probe_cache: dict = {"at": 0.0, "result": None}


class ClosedWeightModelError(ValueError):
    pass


@dataclass
class LLMResult(Generic[T]):
    mode: str                       # LLM_LIVE | LLM_UNAVAILABLE_FALLBACK | LLM_DISABLED
    value: Optional[T] = None       # validated response (LLM_LIVE only)
    model: Optional[str] = None     # model name when LLM_LIVE
    attempts: int = 0
    error: str = ""
    tokens: int = 0

    @property
    def live(self) -> bool:
        return self.mode == LLM_LIVE


@dataclass
class ProbeResult:
    reachable: bool
    base_url: Optional[str] = None
    model: Optional[str] = None
    available_models: list = field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def is_open_weight(model_name: str) -> bool:
    name = model_name.lower().split("/")[-1]
    return any(name.startswith(f) or f"/{f}" in model_name.lower() for f in OPEN_WEIGHT_FAMILIES)


def _require_open_weight(model_name: str) -> str:
    if not is_open_weight(model_name):
        raise ClosedWeightModelError(
            f"Model '{model_name}' is not in the open-weight allowlist {OPEN_WEIGHT_FAMILIES}.")
    return model_name


def llm_disabled() -> bool:
    return os.environ.get("HATCHAI_NO_LLM", "").lower() in ("1", "true", "yes")


def model_name() -> str:
    return _require_open_weight(os.environ.get("HATCHAI_LLM_MODEL") or os.environ.get("OLLAMA_MODEL")
                                or _DEFAULT_MODEL)


ollama_model = model_name  # backwards-compatible alias


def base_urls() -> list[str]:
    raw = os.environ.get("HATCHAI_LLM_BASE_URL") or os.environ.get("OLLAMA_BASE_URL") or _DEFAULT_BASE
    urls = []
    for u in raw.split(","):
        u = u.strip().rstrip("/")
        if u:
            urls.append(u if u.endswith("/v1") else f"{u}/v1")
    return urls


def timeout_s() -> float:
    return float(os.environ.get("HATCHAI_LLM_TIMEOUT") or os.environ.get("OLLAMA_TIMEOUT") or 60)


def retries() -> int:
    return max(0, int(os.environ.get("HATCHAI_LLM_RETRIES", "1")))


def reset_probe_cache() -> None:
    _probe_cache.update(at=0.0, result=None)


# ---------------------------------------------------------------------------
# Probe and mode
# ---------------------------------------------------------------------------

def probe(max_age: float = 30.0) -> ProbeResult:
    """GET {base}/models on each configured URL; reachable only if the configured model is served."""
    if llm_disabled():
        return ProbeResult(False, error="LLM disabled (HATCHAI_NO_LLM=1)")
    now = time.time()
    if _probe_cache["result"] is not None and now - _probe_cache["at"] < max_age:
        return _probe_cache["result"]
    import httpx
    try:
        want = model_name()
    except ClosedWeightModelError as exc:
        res = ProbeResult(False, error=str(exc))
        _probe_cache.update(at=now, result=res)
        return res
    errors = []
    res = None
    for base in base_urls():
        try:
            r = httpx.get(f"{base}/models", timeout=min(3.0, timeout_s()))
            r.raise_for_status()
            ids = [m.get("id", "") for m in (r.json().get("data") or [])]
            if want in ids or f"{want}:latest" in ids:
                res = ProbeResult(True, base, want, ids)
                break
            errors.append(f"{base}: model {want} not served (have {ids[:5]})")
        except Exception as exc:
            errors.append(f"{base}: {type(exc).__name__}")
    res = res or ProbeResult(False, error="; ".join(errors) or "no endpoint configured")
    _probe_cache.update(at=now, result=res)
    return res


def current_mode() -> str:
    if llm_disabled():
        return LLM_DISABLED
    return LLM_LIVE if probe().reachable else LLM_FALLBACK


def active_model_label() -> Optional[str]:
    """Model name if a local endpoint currently serves it, else None."""
    p = probe() if not llm_disabled() else None
    return p.model if p and p.reachable else None


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------

def complete_json(system_prompt: str, user_prompt: str, response_model: Type[T],
                  temperature: float = 0.2, max_tokens: int = 400) -> LLMResult[T]:
    """One schema-validated JSON completion. Never raises; failures become LLM_UNAVAILABLE_FALLBACK."""
    if llm_disabled():
        return LLMResult(LLM_DISABLED, error="LLM disabled (HATCHAI_NO_LLM=1)")
    p = probe()
    if not p.reachable:
        return LLMResult(LLM_FALLBACK, error=p.error or "no local LLM endpoint")
    import httpx
    schema = response_model.model_json_schema()
    body = {
        "model": p.model,
        "messages": [
            {"role": "system", "content": f"{system_prompt}\n\nReply with ONLY one JSON object matching this "
                                          f"JSON schema, no prose:\n{json.dumps(schema)}"},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        # Grammar-constrained structured output (Ollama, llama.cpp, vLLM): small open-weight models
        # otherwise tend to echo the schema back instead of filling it in.
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": response_model.__name__, "schema": schema, "strict": True}},
    }
    last_error, attempts = "", 0
    for attempt in range(1 + retries()):
        attempts = attempt + 1
        try:
            r = httpx.post(f"{p.base_url}/chat/completions", json=body, timeout=timeout_s())
            r.raise_for_status()
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            if not content.strip():
                raise ValueError("empty response")
            value = response_model(**_parse_json(content))
            tokens = int((data.get("usage") or {}).get("total_tokens") or 0)
            return LLMResult(LLM_LIVE, value=value, model=p.model, attempts=attempts, tokens=tokens)
        except httpx.TimeoutException:
            last_error = f"timeout after {timeout_s()} s"
        except (ValidationError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
            last_error = f"invalid response: {type(exc).__name__}: {str(exc)[:160]}"
        except Exception as exc:  # connection errors, HTTP status errors
            last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        log.warning("LLM attempt %s failed: %s", attempts, last_error)
    return LLMResult(LLM_FALLBACK, model=None, attempts=attempts, error=last_error)


def call_llm(system_prompt: str, user_prompt: str, response_model: Type[T],
             temperature: float = 0.3) -> Optional[tuple[T, str, int]]:
    """Backwards-compatible wrapper: (value, model, tokens) when LLM_LIVE, else None."""
    res = complete_json(system_prompt, user_prompt, response_model, temperature)
    return (res.value, res.model, res.tokens) if res.live else None


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    data = json.loads(raw[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON is not an object")
    return data
