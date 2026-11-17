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

orchestrator.OUTPUTS.mkdir(exist_ok=True)   # read orchestrator.OUTPUTS at request time, never cached here


# ---------------------------------------------------------------------------
# HTML helpers — Hatch visual identity (yolk yellow, shell white, warm ink; see static/hatch-logo.jpg)
# ---------------------------------------------------------------------------

import html as _h
import re as _re

STATIC = pathlib.Path(__file__).resolve().parent / "static"

CSS = """
:root{
  --yolk:#FFD000; --yolk-deep:#E8B800; --yolk-tint:#FFF6CC; --shell:#FFFFFF; --ink:#2A1E0F;
  --ink-soft:#5E4E37; --line:#EADFB8; --go:#1E7A4A; --repeat:#2457C5; --pivot:#7442C8; --stop:#C0322B;
  --radius-egg:50% 50% 50% 50% / 60% 60% 42% 42%;
  --display:'Fredoka',ui-rounded,'Arial Rounded MT Bold',system-ui,sans-serif;
  --body:'Atkinson Hyperlegible',system-ui,-apple-system,'Segoe UI',sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--yolk-tint);color:var(--ink);font:16px/1.6 var(--body)}
a{color:var(--ink);text-decoration-color:var(--yolk-deep);text-decoration-thickness:2px;text-underline-offset:3px}
a:hover{text-decoration-color:var(--ink)}
:focus-visible{outline:3px solid var(--ink);outline-offset:3px;border-radius:6px}
code,pre{font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;font-size:.88em}
code{background:#FFF0A8;padding:.1em .35em;border-radius:5px}
h1,h2,h3{font-family:var(--display);font-weight:600;line-height:1.15;margin:0 0 .5em}
h1{font-size:clamp(2rem,4.6vw,3.1rem);letter-spacing:-.01em}
h2{font-size:1.5rem} h3{font-size:1.15rem}
p{margin:0 0 1em}

.top{background:var(--yolk);border-bottom:3px solid var(--ink)}
.top .wrap{display:flex;align-items:center;gap:20px;min-height:76px;flex-wrap:wrap}
.logo{display:block;width:170px;height:62px;background:url(/static/hatch-logo.jpg) -11px -66px/199px auto no-repeat;
  border-radius:8px;flex:none}
.top nav{margin-left:auto;display:flex;gap:18px;font-weight:700}
.top nav a{text-decoration:none;padding:6px 2px;border-bottom:2px solid transparent}
.top nav a:hover{border-bottom-color:var(--ink)}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
main.wrap{padding-top:36px;padding-bottom:64px}

.hero{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:40px;align-items:start}
.lede{font-size:1.15rem;color:var(--ink-soft);max-width:34em}
.panel{background:var(--shell);border:2px solid var(--ink);border-radius:22px;padding:26px}
.panel.flat{border-color:var(--line)}
.field{margin-bottom:16px}
.field label{display:block;font-weight:700;margin-bottom:6px}
.field small{display:block;color:var(--ink-soft);font-size:.85rem;margin-top:4px}
input,textarea{width:100%;font:inherit;color:var(--ink);background:#FFFDF2;border:2px solid var(--line);
  border-radius:12px;padding:11px 13px}
input:focus,textarea:focus{border-color:var(--ink);outline:none;background:#fff}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font:600 1rem var(--display);
  border:2px solid var(--ink);border-radius:999px;padding:11px 20px;cursor:pointer;background:var(--shell);
  color:var(--ink);text-decoration:none;transition:transform .12s ease}
.btn:active{transform:translateY(1px)}
.btn.primary{background:var(--yolk);box-shadow:0 4px 0 var(--ink)}
.btn.primary:hover{background:#FFDA33}
.btn.wide{width:100%;font-size:1.15rem;padding:14px 20px}
.btn.go{background:var(--go);color:#fff;border-color:var(--go)}
.btn.repeat{background:var(--repeat);color:#fff;border-color:var(--repeat)}
.btn.pivot{background:var(--pivot);color:#fff;border-color:var(--pivot)}
.btn.stop{background:var(--shell);color:var(--stop);border-color:var(--stop)}
.btn.quiet{background:transparent}

.steps{list-style:none;margin:0;padding:0;counter-reset:s}
.steps li{counter-increment:s;display:grid;grid-template-columns:34px 1fr;gap:12px;padding:10px 0;
  border-bottom:1px dashed var(--line)}
.steps li:last-child{border-bottom:0}
.steps li::before{content:counter(s);width:30px;height:36px;border-radius:var(--radius-egg);background:var(--yolk);
  border:2px solid var(--ink);display:grid;place-items:center;font:600 .95rem var(--display)}
.steps b{display:block}
.steps span{color:var(--ink-soft);font-size:.92rem}
.muted{color:var(--ink-soft)}
.note{font-size:.9rem;color:var(--ink-soft)}
.examples{margin-top:28px}
.examples ul{margin:.4em 0 0;padding-left:1.1em}

/* Signature: the six phases as eggs, gates as diamonds between them */
.track{display:flex;align-items:flex-start;gap:0;margin:8px 0 30px;overflow-x:auto;padding:10px 4px 4px}
.egg{flex:none;display:flex;flex-direction:column;align-items:center;gap:8px;width:92px;text-align:center}
.egg i{display:block;width:46px;height:58px;border-radius:var(--radius-egg);border:3px solid var(--ink);
  background:var(--shell);position:relative}
.egg.done i{background:radial-gradient(circle at 50% 58%,var(--yolk) 0 46%,var(--shell) 47%)}
.egg.done i::after{content:"";position:absolute;left:4px;right:4px;top:15px;height:8px;
  background:linear-gradient(135deg,transparent 33%,var(--ink) 34% 42%,transparent 43%) 0 0/12px 8px repeat-x}
.egg.now i{background:var(--yolk);animation:wobble 1.6s ease-in-out 1}
.egg.halt i{background:#F4D9D6;border-color:var(--stop)}
.egg small{font-size:.8rem;line-height:1.25;font-weight:700}
.egg em{font-style:normal;font-weight:400;color:var(--ink-soft);display:block}
.gem{flex:1 1 18px;min-width:18px;height:3px;background:var(--line);position:relative;margin-top:28px}
.gem b{position:absolute;left:50%;top:50%;width:14px;height:14px;transform:translate(-50%,-50%) rotate(45deg);
  background:var(--line);border:2px solid var(--shell)}
.gem.go b{background:var(--go)} .gem.repeat b{background:var(--repeat)} .gem.pivot b{background:var(--pivot)}
.gem.stop b{background:var(--stop)} .gem.go,.gem.repeat,.gem.pivot{background:var(--ink)}
@keyframes wobble{0%,100%{transform:rotate(0)}20%{transform:rotate(-7deg)}40%{transform:rotate(6deg)}
  60%{transform:rotate(-4deg)}80%{transform:rotate(2deg)}}
@media (prefers-reduced-motion:reduce){.egg.now i{animation:none}.btn{transition:none}}

.runhead{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:6px}
.pill{display:inline-block;border:2px solid var(--ink);border-radius:999px;padding:2px 12px;font:600 .85rem var(--display);
  background:var(--shell)}
.pill.completed{background:var(--go);border-color:var(--go);color:#fff}
.pill.stopped,.pill.failed{background:var(--stop);border-color:var(--stop);color:#fff}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:28px;align-items:start}
.grid>*,.hero>*{min-width:0}
.doc,.verdict,.panel{overflow-wrap:anywhere}
.verdict{border-radius:22px;border:3px solid var(--ink);background:var(--shell);padding:26px;margin-bottom:24px}
.verdict .word{font:600 clamp(2.6rem,7vw,4.2rem)/1 var(--display);margin:4px 0 12px}
.verdict.go .word{color:var(--go)} .verdict.repeat .word{color:var(--repeat)}
.verdict.pivot .word{color:var(--pivot)} .verdict.stop .word{color:var(--stop)}
.scores{display:flex;gap:26px;flex-wrap:wrap;margin:14px 0 18px}
.scores div{font-size:.9rem;color:var(--ink-soft)}
.scores strong{display:block;font:600 1.6rem var(--display);color:var(--ink)}
.actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.override{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;padding-top:14px;border-top:1px dashed var(--line)}
.override input{flex:1 1 260px}
.banner{border-radius:16px;padding:14px 18px;margin-bottom:20px;border:2px solid var(--ink);background:var(--shell)}
.banner.ok{background:#E2F3E9;border-color:var(--go)} .banner.bad{background:#FBE4E2;border-color:var(--stop)}
.banner.wait{background:var(--yolk)}
.side h3{margin-top:4px}
.files{list-style:none;margin:0;padding:0;font-size:.9rem}
.files li{padding:5px 0;border-bottom:1px dashed var(--line);overflow-wrap:anywhere}
.files li.memo a{font-weight:700}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-family:var(--display);font-weight:600}
.tablebox{overflow-x:auto}
.doc{background:var(--shell);border:2px solid var(--line);border-radius:22px;padding:28px;max-width:900px}
.doc h1{font-size:1.9rem} .doc h2{font-size:1.3rem;margin-top:1.4em} .doc h3{font-size:1.05rem;margin-top:1.2em}
.doc blockquote{margin:0 0 1em;padding:10px 14px;background:var(--yolk-tint);border-left:4px solid var(--yolk-deep);
  border-radius:0 10px 10px 0;color:var(--ink-soft);font-size:.92rem}
.doc ul{padding-left:1.2em} .doc li{margin:.3em 0}
.doc pre{background:var(--ink);color:#FFF6CC;padding:14px;border-radius:12px;overflow-x:auto}
.memo-box{margin-bottom:24px}
.memo-box .doc{max-width:none;padding:22px}
details summary{cursor:pointer;font:600 1.05rem var(--display)}
@media (max-width:860px){.hero,.grid{grid-template-columns:1fr}.logo{width:150px;height:51px;
  background-size:176px auto;background-position:-10px -63px}}
"""


def _e(x) -> str:
    return _h.escape(str(x if x is not None else ""))


def _html(content: str, title: str = "HatchAI") -> HTMLResponse:
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)} · Hatch</title>
<link rel="icon" href="/static/hatch-logo.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Fredoka:wght@500;600&display=swap">
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="logo" href="/" aria-label="Hatch home"></a>
  <nav aria-label="Main"><a href="/">New idea</a><a href="/demo">Example runs</a><a href="/api/runs">All runs (JSON)</a></nav>
</div></header>
<main class="wrap">
{content}
</main>
</body>
</html>""")


def _inline(t: str) -> str:
    t = _re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = _re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = _re.sub(r"(?<![\w*])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", t)
    t = _re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+|/[^)\s]*)\)", r'<a href="\2" rel="noopener">\1</a>', t)
    return t


def md_to_html(text: str) -> str:
    """Small, safe Markdown renderer for our own output files (escape first, then format)."""
    out, para, items, quote, rows, code = [], [], [], [], [], None

    def flush():
        nonlocal para, items, quote, rows
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>"); para = []
        if items:
            out.append("<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + "</ul>"); items = []
        if quote:
            out.append("<blockquote>" + "<br>".join(_inline(q) for q in quote) + "</blockquote>"); quote = []
        if rows:
            body = [r for r in rows if not _re.fullmatch(r"\|?[\s:|-]+\|?", r)]
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in body]
            if cells:
                head = "".join(f"<th>{_inline(c)}</th>" for c in cells[0])
                trs = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
                out.append(f'<div class="tablebox"><table><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table></div>')
            rows = []

    for raw in _h.escape(text).splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if code is None:
                flush(); code = []
            else:
                out.append("<pre>" + "\n".join(code) + "</pre>"); code = None
            continue
        if code is not None:
            code.append(raw); continue
        m = _re.match(r"(#{1,4}) (.*)", line)
        if m:
            flush(); n = min(len(m.group(1)), 3)
            out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>"); continue
        if line.startswith("&gt;"):
            if not quote:
                flush()
            quote.append(line[4:].strip()); continue
        if line.startswith("|"):
            if not rows:
                flush()
            rows.append(line); continue
        m = _re.match(r"\s*(?:[-*]|\d+\.) (.*)", line)
        if m:
            if para or quote or rows:
                flush()
            items.append(m.group(1)); continue
        if not line.strip():
            flush(); continue
        if items and raw.startswith("  "):
            items[-1] += " " + line.strip(); continue
        para.append(line.strip())
    flush()
    if code is not None:
        out.append("<pre>" + "\n".join(code) + "</pre>")
    return "\n".join(out)


PHASES = [("Discover", "live research"), ("Validate", "critique, canvas"), ("Build", "tested MVP"),
          ("Commercial", "pricing; policies MOCKED"), ("Sell", "payments MOCKED"), ("Operate", "real metrics")]


def _track(run_id: str, status: str, phase: int) -> str:
    """Six eggs (phases) with a gate diamond after each of the first five."""
    hist = orchestrator._counters(run_id).get("history", []) if run_id else []
    last = {}
    for h in hist:
        last[h["gate"]] = h["outcome"]
    parts = []
    for i, (name, sub) in enumerate(PHASES, 1):
        if status == "completed" or i < phase:
            cls, state = "done", "done"
        elif i == phase and status in ("stopped", "failed"):
            cls, state = "halt", "stopped here"
        elif i == phase:
            cls, state = "now", "now"
        else:
            cls, state = "", "not started"
        parts.append(f'<div class="egg {cls}"><i aria-hidden="true"></i><small>{i}. {name}<em>{sub}</em></small>'
                     f'<span class="sr-only" style="position:absolute;left:-9999px">{state}</span></div>')
        if i < 6:
            o = last.get(i, "")
            label = f"Gate {i}: {o.upper()}" if o else f"Gate {i}: not reached"
            parts.append(f'<div class="gem {o}" title="{label}" aria-label="{label}"><b></b></div>')
    return f'<div class="track" role="list" aria-label="Six phases and five gates">{"".join(parts)}</div>'


@app.get("/static/hatch-logo.jpg")
def logo():
    from fastapi.responses import FileResponse
    return FileResponse(STATIC / "hatch-logo.jpg", media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    mode = llm_gateway.current_mode()
    label = llm_gateway.active_model_label()
    return _html(f"""
<section class="hero">
  <div>
    <h1>Hatch an idea only when the evidence holds.</h1>
    <p class="lede">Describe a digital product. Hatch researches it on the live web, checks every quote against
    its source, and stops at a gate after each phase. You decide every gate; nothing is published, sent or
    spent without you.</p>
    <form class="panel" action="/api/runs" method="post">
      <div class="field">
        <label for="idea">Your idea</label>
        <textarea id="idea" name="idea" rows="3" required
          placeholder="A spaced-repetition study app for university students in Egypt, in Arabic and English"></textarea>
        <small>Say who it is for, where, and what problem it solves. Vague ideas get a STOP.</small>
      </div>
      <div class="row">
        <div class="field"><label for="tu">Who it's for</label>
          <input id="tu" name="target_user" placeholder="University students"></div>
        <div class="field"><label for="geo">Country</label>
          <input id="geo" name="geography" placeholder="Egypt"></div>
      </div>
      <div class="row">
        <div class="field"><label for="sk">Your skills</label>
          <input id="sk" name="skills" placeholder="Web development"></div>
        <div class="field"><label for="bud">Budget (USD)</label>
          <input id="bud" name="budget_usd" type="number" value="500" min="0"></div>
        <div class="field"><label for="hrs">Hours a week</label>
          <input id="hrs" name="hours_per_week" type="number" value="10" min="1"></div>
      </div>
      <div class="field"><label for="val">Values or limits</label>
        <input id="val" name="values" placeholder="Affordable pricing, no dark patterns"></div>
      <button type="submit" class="btn primary wide">Start research</button>
    </form>
    <p class="note" style="margin-top:14px">Free and keyless: web search, Reddit, Hacker News, Wikipedia and
    World Bank data. Local model: <code>{_e(mode)}{(' · ' + _e(label)) if label else ''}</code>. It only drafts the
    MVP's name, tagline and an optional advisor summary; it never sets a score or a gate.</p>
  </div>
  <aside class="panel flat">
    <h2>What happens next</h2>
    <ol class="steps">
      <li><div><b>Discover</b><span>Live sources, every quote re-checked, each source dated and labelled by who is speaking.</span></div></li>
      <li><div><b>Validate</b><span>Red-team critique, Lean Canvas, and a demand test with thresholds fixed in advance.</span></div></li>
      <li><div><b>Build</b><span>A runnable MVP that must pass its own tests and boot before the gate opens.</span></div></li>
      <li><div><b>Commercial</b><span>Prices from cited competitors, capped by local income data. Policies are MOCKED drafts.</span></div></li>
      <li><div><b>Sell</b><span>Launch drafts wait for your approval. Checkout, refund and reconciliation are a MOCKED simulation.</span></div></li>
      <li><div><b>Operate</b><span>Decides on real visitors only. Test traffic is labelled and never counted.</span></div></li>
    </ol>
    <p class="note" style="margin:14px 0 0">After gates 1–3 an Advisor memo explains what the evidence means:
    the pain, whether the plan addresses it, the weakest assumption and the cheapest test this week.</p>
  </aside>
</section>
""", "New idea")


@app.get("/demo", response_class=HTMLResponse)
def demo_index():
    groups = [
        ("Headline: flashcards for students in Egypt, live research under the strict rule",
         "-headline-v2", "REPEAT → PIVOT → GO, then an MVP that passes 23/23 tests."),
        ("Original strong brief (older, looser relevance rule)", "", "GO at every gate; the Advisor shows the MVP covers 0 of 1 verified pains."),
        ("Weak brief: generic study notes, no user, no country", "-weak-idea", "STOP at Gate 1, before any build or spend."),
        ("Arabic calligraphy workshop booking, Jordan", "-replay-scenario", "REPEAT, then GO after a broader second round."),
    ]
    files = sorted(p.name for p in orchestrator.OUTPUTS.glob("*") if p.is_file())
    suffixes = sorted({v for v in orchestrator.DEMO_RUNS.values() if v}, key=len, reverse=True)

    def suffix_of(name: str) -> str:
        stem = name.rsplit(".", 1)[0]
        return next((x for x in suffixes if stem.endswith(x)), "")

    blocks = []
    for title, suf, what in groups:
        mine = [f for f in files if suffix_of(f) == suf]
        items = "".join(f'<li class="{"memo" if "advisor-memo" in f else ""}"><a href="/outputs/{_e(f)}">{_e(f)}</a></li>'
                        for f in mine)
        blocks.append(f'<section class="panel flat" style="margin-bottom:20px"><h2>{_e(title)}</h2>'
                      f'<p class="muted">{_e(what)}</p><details><summary>{len(mine)} files</summary>'
                      f'<ul class="files" style="margin-top:10px">{items}</ul></details></section>')
    return _html("<h1>Example runs</h1><p class='lede'>Committed demo outputs, replayed offline from evidence "
                 "captured on the live web. Advisor memos are in bold.</p>" + "".join(blocks), "Example runs")


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

_MEMO_STEP = {1: 5, 2: 4, 3: 4}


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_status_page(run_id: str, request: Request):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    status = run["status"]
    phase = run["phase"] or 0
    is_founder = approval.verify_token(run_id, request.cookies.get(f"hatchai_{run_id}", ""))
    running = status.endswith("_running") or status == "running"

    gate_html, memo_html = "", ""
    if "gate_" in status and "pending" in status:
        gate_id = int(status.split("_")[1])
        gate = db.get_gate_result(run_id, gate_id)
        if gate:
            outcome = gate["outcome"]
            allowed = approval.ALLOWED.get(outcome, set())
            labels = {
                "approve": ("go", f"Approve: proceed to Phase {gate_id + 1}"),
                "repeat": ("repeat", "Repeat research (recommended)"),
                "pivot": ("pivot", "Pivot to the suggested angle"),
                "stop": ("stop", "Stop this run"),
            }
            buttons = "".join(
                f'<button class="btn {labels[d][0]}" onclick="decide(&quot;{d}&quot;, &quot;&quot;)">{labels[d][1]}</button>'
                for d in ("approve", "repeat", "pivot", "stop") if d in allowed)
            override = ""
            if "override_stop" in allowed:
                override = """
<div class="override">
  <input id="override_reason" aria-label="Reason for going against the recommendation"
         placeholder="Write why you are going against the recommendation (required)">
  <button class="btn quiet" onclick="decide('override_stop', document.getElementById('override_reason').value)">
    Proceed anyway</button>
</div>"""
            if not is_founder:
                buttons, override = ("<p class='muted' style='margin:0'>Only the founder's browser (token cookie) "
                                     "can decide this gate.</p>"), ""
            pivot_html = (f"<p><strong>Suggested pivot:</strong> {_e(gate.get('pivot_to'))}</p>"
                          if gate.get("pivot_to") else "")
            gate_html = f"""
<section class="verdict {outcome}" aria-live="polite">
  <div class="muted">Gate {gate_id} recommends</div>
  <div class="word">{outcome.upper()}</div>
  <p>{_e(gate['reason'])}</p>
  {pivot_html}
  <div class="scores">
    <div><strong>{gate['evidence_score']}</strong>Evidence score, of 100</div>
    <div><strong>{gate['viability_score'] or '–'}</strong>Viability, of 5</div>
    <div><strong>Code</strong>decided this, not a model</div>
  </div>
  <div class="actions">{buttons}</div>
  {override}
</section>
<script>
function decide(choice, override_reason) {{
  fetch("/api/runs/{run_id}/gates/{gate_id}/decide", {{
    method: "POST", credentials: "same-origin",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{choice, override_reason}})
  }}).then(r => r.json()).then(d => {{
    if (d.ok) location.reload();
    else alert("Not recorded: " + d.error);
  }});
}}
</script>"""
            step = _MEMO_STEP.get(gate_id)
            if step:
                mp = orchestrator.out_dir(run_id) / orchestrator.out_name(run_id, f"phase{gate_id}_step{step}_advisor-memo.md")
                if mp.exists():
                    memo_html = (f'<section class="memo-box"><details open><summary>Advisor memo for Gate {gate_id}: '
                                 f'what the evidence means</summary><div class="doc" style="margin-top:12px">'
                                 f'{md_to_html(mp.read_text(encoding="utf-8"))}</div></details></section>')

    files = orchestrator.list_outputs(run_id)
    file_items = "".join(
        f'<li class="{"memo" if "advisor-memo" in f.name else ""}"><a href="/runs/{run_id}/outputs/{_e(f.name)}">{_e(f.name)}</a></li>'
        for f in files)
    app_state = orchestrator._load(run_id, "app", default={}) or {}
    mvp_html = ""
    if app_state.get("app_dir"):
        rel = pathlib.Path(app_state["app_dir"]).relative_to(orchestrator.ROOT).as_posix()
        mvp_html = (f"<div class='panel flat' style='margin-top:18px'><h3>Your MVP: {_e(app_state['product_name'])}</h3>"
                    f"<p class='note' style='margin:0'>Run it on your machine:<br><code>cd {_e(rel)} &amp;&amp; "
                    f"python server.py --port 8080</code></p></div>")

    log_entries = db.get_log_entries(run_id=run_id, limit=500)[-25:]
    log_rows = "".join(
        f"<tr><td class='muted'>{_e(e['timestamp'][11:19])}</td><td>{_e(e['agent'])}</td>"
        f"<td>{_e(e['action'])}</td><td>{_e(e.get('outcome') or '')}</td></tr>"
        for e in reversed(log_entries))

    banner = ""
    if running:
        banner = '<div class="banner wait" role="status">Working on this phase. The page refreshes by itself.</div>'
    elif status == "completed":
        banner = '<div class="banner ok" role="status">All six phases are done. Read the files on the right, starting with the Advisor memos.</div>'
    elif status == "stopped":
        banner = f'<div class="banner bad" role="status">Run stopped: {_e(run.get("error") or "founder decision")}</div>'
    elif status == "failed":
        banner = f'<div class="banner bad" role="alert">Run failed: {_e(run.get("error") or "unknown error")}</div>'

    content = f"""
<div class="runhead"><h1 style="margin:0">Run {_e(run_id)}</h1>
  <span class="pill {status}">{_e(status.replace('_', ' '))}</span></div>
<p class="muted">{"You are the founder of this run; only you can decide its gates." if is_founder else "You are viewing this run. Only the founder's browser can decide gates."}</p>
{_track(run_id, status, phase)}
<div class="grid">
  <div>
    {banner}
    {gate_html}
    {memo_html}
    <section class="panel flat">
      <h2>Decision log</h2>
      <p class="note">Every agent action, newest first (last 25).</p>
      <div class="tablebox"><table>
        <thead><tr><th>Time</th><th>Agent</th><th>Action</th><th>Outcome</th></tr></thead>
        <tbody>{log_rows or '<tr><td colspan=4 class="muted">No entries yet. The researcher starts in a moment.</td></tr>'}</tbody>
      </table></div>
    </section>
  </div>
  <aside class="side">
    <section class="panel flat">
      <h3>Output files</h3>
      {('<ul class="files">' + file_items + '</ul>') if file_items else '<p class="note" style="margin:0">Files appear here as each phase finishes.</p>'}
    </section>
    {mvp_html}
  </aside>
</div>
<script>
if ({'true' if running or ("gate_" not in status and status not in ("completed", "stopped", "failed")) else 'false'}) {{
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
    return _render_file(orchestrator.OUTPUTS, filename)


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

    back = "/demo" if base == orchestrator.OUTPUTS else "javascript:history.back()"
    body = (md_to_html(content) if filename.endswith(".md") else
            "<pre>" + content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</pre>")
    return _html(f"""
<p><a href="{back}">Back</a></p>
<p class="note" style="margin-bottom:10px"><code>{_e(filename)}</code></p>
<article class="doc">{body}</article>
""", filename)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    label = llm_gateway.active_model_label()
    return {"status": "ok", "model": label, "llm_mode": llm_gateway.current_mode()}
