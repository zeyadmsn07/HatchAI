"""Web layer: founder token lives in the founder's cookie; others cannot decide a gate."""
import time

from fastapi.testclient import TestClient

import db


def _wait(run_id, prefix, timeout=30):
    for _ in range(timeout * 10):
        st = db.get_run(run_id)["status"]
        if st.startswith(prefix) or st in ("failed", "stopped"):
            return st
        time.sleep(0.1)
    return st


def test_web_flow_requires_founder_cookie(strong_collector):
    import app
    founder = TestClient(app.app)
    r = founder.post("/api/runs", data={"idea": "Spaced-repetition flashcards for university students in Egypt",
                                        "target_user": "university students", "geography": "Egypt",
                                        "skills": "web development"}, follow_redirects=False)
    assert r.status_code == 303
    run_id = r.headers["location"].rsplit("/", 1)[-1]
    assert f"hatchai_{run_id}" in founder.cookies
    assert _wait(run_id, "gate_1_pending") == "gate_1_pending"

    page = founder.get(f"/runs/{run_id}").text
    assert "Approve: proceed to Phase 2" in page and db.get_run(run_id)["founder_token"] not in page

    stranger = TestClient(app.app)
    assert "Only the founder" in stranger.get(f"/runs/{run_id}").text
    bad = stranger.post(f"/api/runs/{run_id}/gates/1/decide", json={"choice": "approve"})
    assert bad.status_code == 400 and "token" in bad.json()["error"]
    forged = stranger.post(f"/api/runs/{run_id}/gates/1/decide", json={"choice": "approve", "token": "guess"})
    assert forged.status_code == 400 and "Invalid founder token" in forged.json()["error"]
    assert db.get_gate_result(run_id, 1)["founder_decision"] is None
    assert "founder_token" not in str(stranger.get("/api/runs").json())

    ok = founder.post(f"/api/runs/{run_id}/gates/1/decide", json={"choice": "approve"})
    assert ok.json() == {"ok": True}
    assert _wait(run_id, "gate_2_pending") == "gate_2_pending"


def test_health_reports_model_mode():
    import app
    body = TestClient(app.app).get("/health").json()
    assert body["status"] == "ok" and body["model"] is None
