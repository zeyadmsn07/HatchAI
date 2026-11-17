"""LLM gateway — open-weight models only.

Provider order:
  1. Ollama (local, self-hosted)      OLLAMA_BASE_URL + OLLAMA_MODEL (default qwen3:8b)
  2. Groq free tier (hosted)           GROQ_API_KEY + GROQ_MODEL (default llama-3.3-70b-versatile)

Only open-weight model families are accepted (see OPEN_WEIGHT_FAMILIES). A
closed-weight model name is refused at configuration time, so the system can
never silently present a proprietary model as open-weight.

When no provider is reachable, `call_llm` returns None. Agents then fall back
to their own deterministic, rule-based code path and log `model: null` — no
module in this repository fabricates an "LLM answer" when no model ran.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Families whose weights are publicly downloadable.
OPEN_WEIGHT_FAMILIES = (
    "qwen", "llama", "gemma", "mistral", "mixtral", "phi", "deepseek",
    "gpt-oss", "olmo", "granite", "smollm", "tinyllama",
)

_DEFAULT_OLLAMA_MODEL = "qwen3:8b"
_DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

_ollama_probe: dict = {"checked_at": 0.0, "ok": False}


class ClosedWeightModelError(ValueError):
    pass


def is_open_weight(model_name: str) -> bool:
    name = model_name.lower().split("/")[-1]
    return any(name.startswith(f) or f"/{f}" in model_name.lower() for f in OPEN_WEIGHT_FAMILIES)


def _require_open_weight(model_name: str) -> str:
    if not is_open_weight(model_name):
        raise ClosedWeightModelError(
            f"Model '{model_name}' is not in the open-weight allowlist {OPEN_WEIGHT_FAMILIES}."
        )
    return model_name


def ollama_base_urls() -> list[str]:
    """OLLAMA_BASE_URL may list several URLs (comma-separated); the first that answers is used."""
    raw = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]


def ollama_base_url() -> str:
    return _ollama_probe.get("url") or ollama_base_urls()[0]


def ollama_model() -> str:
    return _require_open_weight(os.environ.get("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL))


def groq_model() -> str:
    return _require_open_weight(os.environ.get("GROQ_MODEL", _DEFAULT_GROQ_MODEL))


def llm_disabled() -> bool:
    return os.environ.get("HATCHAI_NO_LLM", "").lower() in ("1", "true", "yes")


def _ollama_available() -> bool:
    """Probe Ollama at most every 30 s; True only if the configured model is pulled."""
    if llm_disabled():
        return False
    now = time.time()
    if now - _ollama_probe["checked_at"] < 30:
        return _ollama_probe["ok"]
    ok, url = False, None
    import httpx
    for base in ollama_base_urls():
        try:
            r = httpx.get(f"{base}/api/tags", timeout=2.0)
            if r.status_code == 200:
                want = ollama_model()
                names = {m.get("name", "") for m in r.json().get("models", [])}
                ok = want in names or f"{want}:latest" in names
                if ok:
                    url = base
                    break
                log.info("Ollama at %s is up but model %s is not pulled (have: %s)", base, want, sorted(names))
        except Exception:
            continue
    _ollama_probe.update(checked_at=now, ok=ok, url=url)
    return ok


def active_model_label() -> Optional[str]:
    """Model that will be used for the next call, or None for rule-based mode."""
    if llm_disabled():
        return None
    if _ollama_available():
        return f"ollama/{ollama_model()}"
    if os.environ.get("GROQ_API_KEY"):
        return f"groq/{groq_model()}"
    return None


def call_llm(
    system_prompt: str,
    user_prompt: str,
    response_model: Type[T],
    temperature: float = 0.3,
) -> Optional[tuple[T, str, int]]:
    """Return (parsed_response, model_label, tokens_used) or None if no open-weight model answered."""
    if llm_disabled():
        return None
    schema = response_model.model_json_schema()
    system = (
        f"{system_prompt}\n\nReturn ONLY a JSON object that conforms to this JSON schema:\n"
        f"{json.dumps(schema)}\nNo commentary outside the JSON."
    )
    attempts = []
    if _ollama_available():
        attempts.append(("ollama", _call_ollama))
    if os.environ.get("GROQ_API_KEY"):
        attempts.append(("groq", _call_groq))

    for name, fn in attempts:
        try:
            raw, label, tokens = fn(system, user_prompt, schema, temperature)
            data = _parse_json(raw)
            return response_model(**data), label, tokens
        except (ValidationError, ValueError, KeyError) as exc:
            log.warning("%s returned invalid JSON for %s: %s", name, response_model.__name__, exc)
        except Exception as exc:  # network etc.
            log.warning("%s call failed: %s", name, exc)
    return None


def _call_ollama(system: str, user: str, schema: dict, temperature: float):
    import httpx
    model = ollama_model()
    r = httpx.post(
        f"{ollama_base_url()}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": schema,
            "stream": False,
            "think": False,
            "options": {"temperature": temperature},
        },
        timeout=float(os.environ.get("OLLAMA_TIMEOUT", "300")),
    )
    r.raise_for_status()
    body = r.json()
    tokens = int(body.get("prompt_eval_count", 0) or 0) + int(body.get("eval_count", 0) or 0)
    return body["message"]["content"], f"ollama/{model}", tokens


def _call_groq(system: str, user: str, schema: dict, temperature: float):
    import httpx
    model = groq_model()
    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    r.raise_for_status()
    body = r.json()
    tokens = int(body.get("usage", {}).get("total_tokens", 0) or 0)
    return body["choices"][0]["message"]["content"], f"groq/{model}", tokens


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(raw[start:end + 1])
