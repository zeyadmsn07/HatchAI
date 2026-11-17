"""FastAPI application — HatchAI web dashboard.

Routes:
  GET  /                          → brief submission form
  POST /api/runs                  → start a new run
  GET  /runs/{run_id}             → status/progress page
  GET  /api/runs/{run_id}/status  → JSON status (for polling)
  POST /api/runs/{run_id}/gates/{n}/decide → founder gate decision
  GET  /api/runs                  → list all runs (JSON)
  GET  /runs/{run_id}/outputs/{f} → view an output file of a run
  GET  /outputs/{filename}        → view a committed demo output file
  GET  /health                    → health check
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from datetime import datetime, timezone

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

import llm_gateway

import db
import approval
import orchestrator

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

db.init_db()

app = FastAPI(title="HatchAI", version="1.0.0")

OUTPUTS = orchestrator.OUTPUTS
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
      <strong>No API keys required.</strong> Language steps use a local open-weight model via Ollama
      (<code>OLLAMA_MODEL</code>, default <code>qwen3:8b</code>) or Groq's free tier (Llama 3.3 70B).
      Without a model, agents run in labelled rule-based / extractive mode. Research uses live, cited web sources.
      Currently active model: <code>""" + (llm_gateway.active_model_label() or "none (rule-based mode)") + """</code>.
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
    # The founder token lives in an HttpOnly cookie on the founder's browser only.
    resp = RedirectResponse(f"/runs/{run_id}", status_code=303)
    resp.set_cookie(f"hatchai_{run_id}", run["founder_token"], httponly=True, samesite="strict")
    return resp


# ---------------------------------------------------------------------------
# Status page
# ---------------------------------------------------------------------------

@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_status_page(run_id: str, request: Request):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    status = run["status"]
    phase = run["phase"] or 0
    is_founder = approval.verify_token(run_id, request.cookies.get(f"hatchai_{run_id}", ""))

    # Phase progress
    phase_names = [
        "Discover (live sources)",
        "Validate (demand test: STUBBED execution)",
        "Build (generated + tested MVP)",
        "Commercial (policies: MOCKED)",
        "Launch (payments: MOCKED, posting: STUBBED)",
        "Operate & Learn (analytics: STUBBED)",
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
            allowed = approval.ALLOWED.get(outcome, set())
            labels = {
                "approve": ("btn-success", f"Approve: proceed to Phase {gate_id + 1}"),
                "repeat": ("btn-warning", "Repeat (as recommended)"),
                "pivot": ("btn-info", "Pivot to suggested angle"),
                "stop": ("btn-danger", "Stop this run"),
            }
            buttons = "".join(
                f'<button class="btn {labels[d][0]} btn-sm" onclick="decide(&quot;{d}&quot;, &quot;&quot;)">{labels[d][1]}</button>'
                for d in ("approve", "repeat", "pivot", "stop") if d in allowed)
            if "override_stop" in allowed:
                buttons += """
<input id="override_reason" class="form-control form-control-sm" style="max-width:360px"
       placeholder="Written reason required to proceed against the recommendation">
<button class="btn btn-outline-secondary btn-sm"
  onclick="decide('override_stop', document.getElementById('override_reason').value)">
  Proceed anyway (override)
</button>"""
            pivot_html = f"<p class='small'><b>Suggested pivot:</b> {gate.get('pivot_to')}</p>" if gate.get("pivot_to") else ""
            if not is_founder:
                buttons = "<span class='small text-muted'>Only the founder's browser (token cookie) can decide this gate.</span>"
            gate_html = f"""
<div class="card gate-card {color_cls} mb-4">
  <div class="card-body">
    <h5 class="card-title">Gate {gate_id}: recommendation <strong>{outcome.upper()}</strong></h5>
    <p class="card-text small">{gate['reason']}</p>
    {pivot_html}
    <p class="small text-muted">
      Evidence score: {gate['evidence_score']} &nbsp;|&nbsp;
      Viability score: {gate['viability_score']} &nbsp;|&nbsp; computed by code, not by an LLM
    </p>
    <div class="d-flex gap-2 flex-wrap align-items-center">{buttons}</div>
  </div>
</div>
<script>
function decide(choice, override_reason) {{
  fetch("/api/runs/{run_id}/gates/{gate_id}/decide", {{
    method: "POST", credentials: "same-origin",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{choice, override_reason}})
  }}).then(r => r.json()).then(d => {{
    if (d.ok) location.reload();
    else alert("Error: " + d.error);
  }});
}}
</script>"""

    # Output files
    outputs_html = ""
    files = orchestrator.list_outputs(run_id)
    if files:
        outputs_html = "<h6 class='mt-3'>Output Files</h6><ul class='list-unstyled'>"
        for f in files:
            outputs_html += f'<li><a href="/runs/{run_id}/outputs/{f.name}" class="small">{f.name}</a></li>'
        outputs_html += "</ul>"
    app_state = orchestrator._load(run_id, "app", default={}) or {}
    if app_state.get("app_dir"):
        rel = pathlib.Path(app_state["app_dir"]).relative_to(orchestrator.ROOT).as_posix()
        outputs_html += (f"<p class='small mt-2'><b>Generated MVP:</b> {app_state['product_name']}<br>"
                         f"<code>cd {rel} &amp;&amp; python server.py --port 8080</code></p>")

    # Decision log
    log_entries = db.get_log_entries(run_id=run_id, limit=500)[-25:]
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
          {"You are the founder of this run." if is_founder else "Viewer (no founder token)."}
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
      <div class="card-header small">Decision Log (last 25 entries)</div>
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
    token = body.get("token") or request.cookies.get(f"hatchai_{run_id}", "")
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
    return [{k: v for k, v in r.items() if k != "founder_token"} for r in db.get_all_runs()]


@app.get("/api/runs/{run_id}/log")
def api_run_log(run_id: str):
    return db.get_log_entries(run_id=run_id)


# ---------------------------------------------------------------------------
# Output file viewer
# ---------------------------------------------------------------------------

@app.get("/runs/{run_id}/outputs/{filename}")
def view_run_output(run_id: str, filename: str):
    if not db.get_run(run_id):
        raise HTTPException(404)
    return _render_file(orchestrator.out_dir(run_id), filename)


@app.get("/outputs/{filename}")
def view_output(filename: str):
    return _render_file(OUTPUTS, filename)


def _render_file(base: pathlib.Path, filename: str):
    path = base / filename
    if not path.resolve().is_relative_to(base.resolve()):
        raise HTTPException(403, "Path traversal not allowed")
    if not path.exists():
        raise HTTPException(404, f"Output file {filename} not found")

    content = path.read_text(encoding="utf-8")

    if filename.endswith(".json"):
        return JSONResponse(json.loads(content))

    if filename.endswith(".html"):
        return PlainTextResponse(content)

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
    label = llm_gateway.active_model_label()
    return {"status": "ok", "model": label, "mode": "llm" if label else "rule-based (no LLM reachable)"}
