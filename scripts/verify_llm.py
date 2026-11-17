"""Verify the open-weight LLM path against a LOCAL OpenAI-compatible endpoint.

    python scripts/verify_llm.py
    HATCHAI_LLM_BASE_URL=http://localhost:8080/v1 HATCHAI_LLM_MODEL=qwen2.5-0.5b-instruct python scripts/verify_llm.py

Steps:
  1. Resource check: free disk (repo drive and home drive) and free memory. If disk < 2 GB or
     memory < 1 GB, it says so and attempts nothing heavy (no model call).
  2. Probe GET {base}/models on each configured URL and check the configured model is served.
  3. One real round-trip through the same client the pipeline uses (llm_gateway.complete_json):
     a tiny schema-validated JSON answer.

Exit codes: 0 VERIFIED (a model answered and passed validation) | 1 NOT VERIFIED: no local LLM
endpoint | 2 NOT VERIFIED: resources too low | 3 NOT VERIFIED: endpoint reachable but the
round-trip failed. Downloads nothing and installs nothing.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel  # noqa: E402

import llm_gateway  # noqa: E402

MIN_DISK_GB = 2.0
MIN_MEM_GB = 1.0


class Ping(BaseModel):
    answer: str
    number: int


def free_memory_gb() -> float | None:
    try:
        if sys.platform == "win32":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullAvailPhys / 1024 ** 3
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024 ** 2
    except Exception:
        return None
    return None


def resources() -> dict:
    disks = {}
    for label, path in (("repo drive", ROOT), ("home drive", Path.home())):
        try:
            disks[f"{label} ({path.anchor or path})"] = shutil.disk_usage(path).free / 1024 ** 3
        except OSError:
            pass
    return {"disk_free_gb": disks, "mem_free_gb": free_memory_gb()}


def main() -> int:
    print("HatchAI LLM verification (local OpenAI-compatible endpoint only)")
    print(f"  base URL(s): {', '.join(llm_gateway.base_urls())}")
    try:
        print(f"  model:       {llm_gateway.model_name()}")
    except llm_gateway.ClosedWeightModelError as exc:
        print(f"NOT VERIFIED: {exc}")
        return 1
    if llm_gateway.llm_disabled():
        print("NOT VERIFIED: LLM is disabled (HATCHAI_NO_LLM=1); unset it to verify.")
        return 1

    r = resources()
    for k, v in r["disk_free_gb"].items():
        print(f"  free disk, {k}: {v:.2f} GB")
    mem = r["mem_free_gb"]
    print(f"  free memory: {'unknown' if mem is None else f'{mem:.2f} GB'}")
    low = [k for k, v in r["disk_free_gb"].items() if v < MIN_DISK_GB]
    if low or (mem is not None and mem < MIN_MEM_GB):
        why = (f"free disk under {MIN_DISK_GB:.0f} GB on {', '.join(low)}" if low else "") + \
              (("; " if low else "") + f"free memory under {MIN_MEM_GB:.0f} GB" if mem is not None and mem < MIN_MEM_GB else "")
        print(f"  resources low: {why}. Attempting nothing heavy (no model call).")
        p = llm_gateway.probe(max_age=0)
        print(f"  endpoint probe only: {'reachable, serves ' + p.model if p.reachable else 'not reachable (' + p.error + ')'}")
        if not p.reachable:
            print("NOT VERIFIED: no local LLM endpoint (resources are also too low for a model round-trip)")
            return 1
        print("NOT VERIFIED: resources too low for a model round-trip on this machine")
        return 2

    llm_gateway.reset_probe_cache()
    p = llm_gateway.probe(max_age=0)
    if not p.reachable:
        print(f"  probe: {p.error}")
        print("NOT VERIFIED: no local LLM endpoint")
        return 1
    print(f"  probe: {p.base_url} serves {p.model} ({len(p.available_models)} model(s) listed)")
    t0 = time.time()
    res = llm_gateway.complete_json("You are a test endpoint.",
                                    'Return {"answer": "ok", "number": 7} exactly.', Ping, temperature=0.0,
                                    max_tokens=40)
    dt = time.time() - t0
    if res.live:
        print(f"  round-trip: {res.mode}, model {res.model}, {res.attempts} attempt(s), {dt:.1f} s, "
              f"validated answer {res.value.model_dump()}")
        print(f"VERIFIED: local endpoint {p.base_url} with model {res.model} answered and passed schema validation")
        return 0
    print(f"  round-trip: {res.mode} after {res.attempts} attempt(s), {dt:.1f} s: {res.error}")
    print("NOT VERIFIED: endpoint reachable but the round-trip failed")
    return 3


if __name__ == "__main__":
    sys.exit(main())
