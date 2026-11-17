"""Send clearly labelled TEST traffic to a generated MVP to verify the demand-test pipeline.

This is NOT demand. Every request carries `X-HatchAI-Traffic: TEST`, every TEST visitor id
starts with `test-`, and every TEST sign-up uses the reserved @example.com domain. The MVP
stores these as TEST events, and Phase 6 reports them separately from real traffic.

    python demand_test_traffic.py generated_mvps/demo-strong --visitors 300 --signups 20

The script starts the MVP as a child process on a free port with its persistent `app.db`,
sends the traffic over HTTP, reads /api/metrics, and stops only that child process.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

HEADERS = {"X-HatchAI-Traffic": "TEST", "Content-Type": "application/json"}


def _request(url: str, body: dict | None = None, extra: dict | None = None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={**HEADERS, **(extra or {})},
                                 method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=5) as r:
        raw = r.read()
        return json.loads(raw) if "json" in r.headers.get("Content-Type", "") else None


def send_test_traffic(app_dir: str | Path, visitors: int = 300, signups: int = 20, db_name: str = "app.db") -> dict:
    """Run the MVP, send TEST visits/sign-ups, return {'sent': ..., 'metrics': ...}."""
    app_dir = Path(app_dir)
    if not (app_dir / "server.py").exists():
        raise FileNotFoundError(f"{app_dir} is not a generated MVP (no server.py)")
    if signups > visitors:
        raise ValueError("signups cannot exceed visitors")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from agents.builder import start_mvp_server   # OS-assigned port, no reserve-then-release race
    proc, port = start_mvp_server(app_dir, db_name)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                _request(base + "/health")
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("MVP did not start")
        run_tag = f"{time.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"   # unique per batch, even within one second
        for i in range(visitors):
            _request(base + "/", extra={"Cookie": f"hatchai_vid=test-{run_tag}-{i:04d}"})
        for i in range(signups):
            _request(base + "/api/waitlist", {"email": f"test-{run_tag}-{i:04d}@example.com", "consent": True})
        metrics = _request(base + "/api/metrics")
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    return {"label": "TEST", "sent": {"visitors": visitors, "signups": signups}, "metrics": metrics,
            "db": str(app_dir / db_name)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("app_dir")
    ap.add_argument("--visitors", type=int, default=300)
    ap.add_argument("--signups", type=int, default=20)
    a = ap.parse_args()
    print(json.dumps(send_test_traffic(a.app_dir, a.visitors, a.signups), indent=2))
