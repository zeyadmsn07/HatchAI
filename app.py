"""FastAPI application — HatchAI web dashboard.

Routes:
  GET  /                          → brief submission form
  POST /api/runs                  → start a new run
  GET  /runs/{run_id}             → status/progress page
  GET  /api/runs/{run_id}/status  → JSON status (for polling)
  POST /api/runs/{run_id}/gates/{n}/decide → founder gate decision
  GET  /api/runs                  → list all runs (JSON)
  GET  /outputs/{filename}        → view an output file
  GET  /health                    → health check
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from datetime import datetime, timezone

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

import db
import approval
import orchestrator

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

db.init_db()

app = FastAPI(title="HatchAI", version="1.0.0")

OUTPUTS = pathlib.Path("outputs")
OUTPUTS.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _html(content: str, title: str = "HatchAI") -> HTMLResponse:
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — HatchAI</title>
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
<style>
  body {{ background:#f8f9fa; }}
  .badge-mocked {{ background:#ffc107; color:#000; }}
  .badge-working {{ background:#198754; color:#fff; }}
  .badge-stubbed {{ background:#6c757d; color:#fff; }}
  pre {{ background:#1e1e1e; color:#d4d4d4; padding:1rem; border-radius:6px; overflow-x:auto; }}
  .gate-card {{ border-left: 4px solid #0d6efd; }}
  .gate-stop {{ border-left-color: #dc3545 !important; }}
  .gate-go {{ border-left-color: #198754 !important; }}
  .gate-repeat {{ border-left-color: #ffc107 !important; }}
</style>
</head>
<body>
<nav class="navbar navbar-dark bg-dark mb-4">
  <div class="container">
    <a class="navbar-brand fw-bold" href="/">🚀 HatchAI</a>
    <span class="text-white-50 small">Evidence-gated venture builder · offline-capable</span>
    <a href="/api/runs" class="text-white-50 small">All runs</a>
  </div>
</nav>
<div class="container pb-5">
{content}
</div>
</body>
</html>""")


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    return _html("""
<div class="row justify-content-center">
  <div class="col-lg-8">
    <h1 class="mb-1">Turn your idea into a validated digital product</h1>
    <p class="text-muted mb-4">
      Six evidence-gated phases · Founder approval at every gate ·
      Works offline with no API keys · All mocked parts clearly labelled.
    </p>
    <div class="card shadow-sm">
      <div class="card-body p-4">
        <form action="/api/runs" method="post">
          <div class="mb-3">
            <label class="form-label fw-semibold">Your idea *</label>
            <textarea name="idea" class="form-control" rows="3" required
              placeholder="e.g. An Arabic-first spaced-repetition study app for Egyptian university students"></textarea>
          </div>
          <div class="row g-3 mb-3">
            <div class="col-md-6">
              <label class="form-label">Target user</label>
              <input name="target_user" class="form-control"
                placeholder="e.g. University students aged 18-25">
            </div>
            <div class="col-md-6">
              <label class="form-label">Geography</label>
              <input name="geography" class="form-control" placeholder="e.g. Egypt">
            </div>
          </div>
          <div class="row g-3 mb-3">
            <div class="col-md-4">
              <label class="form-label">Your skills</label>
              <input name="skills" class="form-control" placeholder="e.g. web development">
            </div>
            <div class="col-md-4">
              <label class="form-label">Budget (USD)</label>
              <input name="budget_usd" type="number" class="form-control" value="500" min="0">
            </div>
            <div class="col-md-4">
              <label class="form-label">Hours / week</label>
              <input name="hours_per_week" type="number" class="form-control" value="10" min="1">
            </div>
          </div>
          <div class="mb-3">
            <label class="form-label">Values / constraints</label>
            <input name="values" class="form-control"
              placeholder="e.g. accessibility, affordable pricing, no dark patterns">
          </div>
          <button type="submit" class="btn btn-primary btn-lg w-100">
            Start Analysis →
          </button>
        </form>
      </div>
    </div>
    <div class="mt-4 small text-muted">
      <strong>No API keys required.</strong> The pipeline runs in offline mock mode
      when <code>GEMINI_API_KEY</code> / <code>GROQ_API_KEY</code> are absent.
      All synthetic outputs are labelled ASSUMPTION or MOCKED.
    </div>
  </div>
</div>
""", "New Run")


# ---------------------------------------------------------------------------
# Start run
# ---------------------------------------------------------------------------

@app.post("/api/runs", response_class=HTMLResponse)
def create_run(
    idea: str = Form(...),
    target_user: str = Form(default=""),
    geography: str = Form(default=""),
    skills: str = Form(default=""),
    budget_usd: float = Form(default=500),
    hours_per_week: float = Form(default=10),
    values: str = Form(default=""),
):
    brief_text = idea
    if target_user:
        brief_text += f"\nTarget user: {target_user}"
    if geography:
        brief_text += f"\nGeography: {geography}"
    if skills:
        brief_text += f"\nSkills: {skills}"
    brief_text += f"\nBudget: ${budget_usd}"
    brief_text += f"\nHours per week: {hours_per_week}"
    if values:
        brief_text += f"\nValues: {values}"

    run_id = orchestrator.start_run(brief_text)
    run = db.get_run(run_id)

    # Return redirect to status page
    return HTMLResponse(
        f'<meta http-equiv="refresh" content="0; url=/runs/{run_id}">',
        status_code=200,
    )


# ---------------------------------------------------------------------------
# Status page
# ---------------------------------------------------------------------------

@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_status_page(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    status = run["status"]
    phase = run["phase"] or 0
    founder_token = run["founder_token"]

    # Phase progress
    phase_names = [
        "Discover", "Validate", "Build",
        "Commercial", "Launch", "Operate & Learn"
    ]
    progress_html = ""
    for i, name in enumerate(phase_names, 1):
        active = "fw-bold text-primary" if i == phase else ""
        done = "text-success" if i < phase or status == "completed" else ""
        cls = active or done or "text-muted"
        icon = "✓" if (i < phase or status == "completed") else ("▶" if i == phase else "○")
        progress_html += f'<li class="list-group-item {cls}">{icon} Phase {i}: {name}</li>'

    # Gate decision card
    gate_html = ""
    if "gate_" in status and "pending" in status:
        gate_id = int(status.split("_")[1])
        gate = db.get_gate_result(run_id, gate_id)
        if gate:
            outcome = gate["outcome"]
            color_cls = {"go": "gate-go", "stop": "gate-stop", "repeat": "gate-repeat", "pivot": "gate-repeat"}.get(outcome, "")
            override_input = ""
            if outcome == "stop":
                override_input = """
<div class="mb-2">
  <input id="override_reason" class="form-control form-control-sm"
         placeholder="Written reason required to override STOP">
</div>
<button class="btn btn-warning btn-sm"
  onclick="decide('override_stop', document.getElementById('override_reason').value)">
  Override STOP (requires reason)
</button>"""
            gate_html = f"""
<div class="card gate-card {color_cls} mb-4">
  <div class="card-body">
    <h5 class="card-title">Gate {gate_id} — <strong>{outcome.upper()}</strong></h5>
    <p class="card-text">{gate['reason']}</p>
    <p class="small text-muted">
      Evidence score: {gate['evidence_score']} &nbsp;|&nbsp;
      Viability score: {gate['viability_score']}
    </p>
    <div class="d-flex gap-2 flex-wrap align-items-center">
      <button class="btn btn-success btn-sm" onclick="decide('approve', '')">
        ✓ Approve — proceed to Phase {gate_id + 1}
      </button>
      <button class="btn btn-danger btn-sm" onclick="decide('stop', '')">
        ✗ Stop this run
      </button>
      {override_input}
    </div>
  </div>
</div>
<script>
function decide(choice, override_reason) {{
  const token = "{founder_token}";
  fetch("/api/runs/{run_id}/gates/{gate_id}/decide", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{choice, token, override_reason}})
  }}).then(r => r.json()).then(d => {{
    if (d.ok) location.reload();
    else alert("Error: " + d.error);
  }});
}}
</script>"""

    # Output files
    outputs_html = ""
    if OUTPUTS.exists():
        files = sorted(OUTPUTS.glob("*.md")) + sorted(OUTPUTS.glob("*.json")) + sorted(OUTPUTS.glob("*.html"))
        if files:
            outputs_html = "<h6 class='mt-3'>Output Files</h6><ul class='list-unstyled'>"
            for f in files:
                outputs_html += f'<li><a href="/outputs/{f.name}" class="small">{f.name}</a></li>'
            outputs_html += "</ul>"

    # Decision log
    log_entries = db.get_log_entries(run_id=run_id, limit=20)
    log_rows = "".join(
        f"<tr><td class='text-muted small'>{e['timestamp'][:19]}</td>"
        f"<td class='small'>{e['agent']}</td>"
        f"<td class='small'>{e['action']}</td>"
        f"<td class='small'>{e.get('outcome') or ''}</td></tr>"
        for e in log_entries
    )

    status_badge = {
        "completed": "bg-success",
        "stopped": "bg-danger",
        "failed": "bg-danger",
    }.get(status, "bg-primary")

    content = f"""
<div class="row">
  <div class="col-md-3">
    <div class="card mb-3">
      <div class="card-body">
        <h6 class="card-title">Run ID</h6>
        <code class="small">{run_id}</code>
        <div class="mt-2">
          <span class="badge {status_badge}">{status.replace('_', ' ')}</span>
        </div>
        <p class="small text-muted mt-2">
          Founder token:<br><code class="small">{founder_token}</code>
        </p>
      </div>
    </div>
    <ul class="list-group list-group-flush small">
      {progress_html}
    </ul>
    {outputs_html}
  </div>
  <div class="col-md-9">
    {"" if status not in ("running", "phase_1_running", "phase_2_running", "phase_3_running",
                           "phase_4_running", "phase_5_running", "phase_6_running")
       else '<div class="alert alert-info">Pipeline running… <span id="dots">.</span></div>'}
    {"<div class='alert alert-success'>✓ All phases complete!</div>" if status == "completed" else ""}
    {"<div class='alert alert-danger'>Run stopped: " + (run.get('error') or 'founder decision') + "</div>" if status == "stopped" else ""}
    {"<div class='alert alert-danger'>Run failed: " + (run.get('error') or 'unknown error') + "</div>" if status == "failed" else ""}
    {gate_html}
    <div class="card">
      <div class="card-header small">Decision Log (last 20 entries)</div>
      <div class="card-body p-0">
        <table class="table table-sm mb-0">
          <thead><tr>
            <th class="small">Time</th><th class="small">Agent</th>
            <th class="small">Action</th><th class="small">Outcome</th>
          </tr></thead>
          <tbody>{log_rows or '<tr><td colspan=4 class="text-muted small p-2">No entries yet</td></tr>'}</tbody>
        </table>
      </div>
    </div>
  </div>
</div>
<script>
// Auto-refresh while pipeline is running
const status = "{status}";
if (!["completed","stopped","failed"].includes(status)) {{
  let dots = 0;
  setInterval(() => {{
    dots = (dots + 1) % 4;
    const el = document.getElementById("dots");
    if (el) el.textContent = ".".repeat(dots + 1);
  }}, 500);
  setTimeout(() => location.reload(), 3000);
}}
</script>
"""
    return _html(content, f"Run {run_id}")


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

@app.get("/api/runs/{run_id}/status")
def api_run_status(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404)
    return {"run_id": run_id, "status": run["status"], "phase": run["phase"]}


@app.post("/api/runs/{run_id}/gates/{gate_id}/decide")
async def api_gate_decide(run_id: str, gate_id: int, request: Request):
    body = await request.json()
    choice = body.get("choice", "")
    token = body.get("token", "")
    override_reason = body.get("override_reason", "")

    if not choice or not token:
        return JSONResponse({"ok": False, "error": "choice and token required"}, 400)

    ok, err = approval.record_decision(run_id, gate_id, choice, token, override_reason)
    if not ok:
        return JSONResponse({"ok": False, "error": err}, 400)

    orchestrator.advance_after_gate(run_id, gate_id, choice)
    return {"ok": True}


@app.get("/api/runs")
def api_list_runs():
    return db.get_all_runs()


@app.get("/api/runs/{run_id}/log")
def api_run_log(run_id: str):
    return db.get_log_entries(run_id=run_id)


# ---------------------------------------------------------------------------
# Output file viewer
# ---------------------------------------------------------------------------

@app.get("/outputs/{filename}")
def view_output(filename: str):
    path = OUTPUTS / filename
    if not path.exists():
        raise HTTPException(404, f"Output file {filename} not found")
    if not path.resolve().is_relative_to(OUTPUTS.resolve()):
        raise HTTPException(403, "Path traversal not allowed")

    content = path.read_text(encoding="utf-8")

    if filename.endswith(".json"):
        return JSONResponse(json.loads(content))

    if filename.endswith(".html"):
        return HTMLResponse(content)

    # Render Markdown-ish text in a simple pre block
    escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return _html(f"""
<div class="row justify-content-center">
  <div class="col-lg-10">
    <h5 class="mb-3"><a href="javascript:history.back()">← back</a> &nbsp; {filename}</h5>
    <pre>{escaped}</pre>
  </div>
</div>
""", filename)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "offline_mode": not bool(
        __import__("os").environ.get("GEMINI_API_KEY") or
        __import__("os").environ.get("GROQ_API_KEY")
    )}
