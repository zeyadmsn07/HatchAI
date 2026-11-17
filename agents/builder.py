"""Builder agent — generates a runnable, tested, idea-specific MVP.

Method (Phase 3):
 1. Classify the validated idea into an archetype with tested domain logic
    (spaced_repetition, booking, habit_tracker, directory, course).
 2. Build an AppSpec: product name, fields, features traced to Lean Canvas
    problems/risks, sample seed content. An open-weight LLM (if available) may
    write the name, tagline and seed content — never code. Seeds are validated
    by the archetype's own `validate()` before use.
 3. Render the app into generated_mvps/<run_id>/ (stdlib-only Python: SQLite
    store, JSON API, web UI, consented waitlist for the demand test).
 4. Generate an idea-specific spec test file, then actually run the full test
    suite in a subprocess and boot the server for a smoke test.
 5. Report everything to Gate 3. A failed build is retried once without LLM
    seed content; a second failure is a STOP.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import callbacks
import evidence
import gates
import llm_gateway
from models import (AppSpec, Critique, FeatureSpec, FieldSpec, FounderBrief, LeanCanvas, SpecText,
                    TemplateSuggestion)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "mvp_templates"
GENERATED = ROOT / "generated_mvps"
SPEC_PROMPT = ROOT / "prompts" / "builder.md"
TEMPLATE_PROMPT = ROOT / "prompts" / "template_suggester.md"

# Template compatibility keywords: stem -> weight. A stem matches at the start of a word
# ("schedul" matches "scheduling") and counts once per idea, however often it repeats.
# Weight 2 = names the template's core job; weight 1 = suggestive but ambiguous on its own.
ARCHETYPE_KEYWORDS = {
    "spaced_repetition": {"flashcard": 2, "flash card": 2, "spaced": 2, "repetition": 2, "anki": 2,
                          "memoriz": 2, "memoris": 2, "vocabulary": 2,
                          "quiz": 1, "revision": 1, "exam prep": 1, "recall": 1},
    "booking": {"booking": 2, "appointment": 2, "reservation": 2,
                "book": 1, "schedul": 1, "slot": 1, "session": 1, "calendar": 1},
    "habit_tracker": {"habit": 2, "streak": 2,
                      "track": 1, "routine": 1, "journal": 1, "goal": 1},
    "directory": {"marketplace": 2, "directory": 2, "listing": 2,
                  "find": 1, "freelanc": 1, "jobs": 1, "rent": 1, "connect": 1, "match": 1,
                  "local services": 1, "vendor": 1},
    "course": {"course": 2, "lesson": 2, "curriculum": 2, "learning path": 2, "cohort": 2, "bootcamp": 2,
               "tutorial": 1, "template": 1, "ebook": 1, "guide": 1, "training": 1, "workshop": 1},
}
SUFFIX = {"spaced_repetition": "Recall", "booking": "Book", "habit_tracker": "Streaks",
          "directory": "Finder", "course": "Academy"}
TAGLINE = {"spaced_repetition": "Flashcards that schedule each review for you (SM-2)",
           "booking": "Book sessions without double-bookings or clashes",
           "habit_tracker": "Daily check-ins, streaks and weekly targets",
           "directory": "Find the right listing fast and contact the owner",
           "course": "A self-paced course that always shows your next step"}
GENERIC = {"ai-powered", "ai", "app", "tool", "study", "platform", "simple", "smart", "mobile", "web",
           "build", "want", "focused", "subjects", "university", "students", "online", "sells", "generic"}


MAX_SYNONYM_CREDIT = 1   # an accepted LLM synonym adds at most +1 to one template's score


def accept_synonyms(text: str, suggestion, deterministic_matched: dict) -> dict[str, list[tuple[str, str]]]:
    """Keep only LLM synonyms that code can check: the phrase occurs verbatim in the idea,
    the keyword is an existing, not-yet-matched keyword of that template, and the template
    already has at least one deterministic keyword match (the LLM can top up, never invent)."""
    a = getattr(suggestion, "template", None)
    if a not in ARCHETYPE_KEYWORDS or not deterministic_matched.get(a):
        return {}
    low = text.lower()
    kept: list[tuple[str, str]] = []
    for s in getattr(suggestion, "synonyms", [])[:5]:
        phrase, kw = s.phrase.strip().lower(), s.keyword.strip().lower()
        if not (3 <= len(phrase) <= 40) or kw not in ARCHETYPE_KEYWORDS[a] or kw in deterministic_matched[a]:
            continue
        if re.search(rf"\b{re.escape(phrase)}\b", low) and kw not in {k for _, k in kept}:
            kept.append((phrase, kw))
    return {a: kept[:MAX_SYNONYM_CREDIT]} if kept else {}


def select_template(text: str, synonyms: dict[str, list[tuple[str, str]]] | None = None) -> dict:
    """Pick a tested template only when the idea clearly fits one.

    Returns {"archetype": str | None, "supported": bool, "scores", "matched", "reason"}.
    Supported only if the best score >= gate_3.min_template_score AND it beats the
    runner-up by >= gate_3.min_template_margin. Otherwise archetype is None — there is
    no default template. `synonyms` (already filtered by accept_synonyms) add +1 each,
    capped at MAX_SYNONYM_CREDIT per template, and face the same thresholds.
    """
    cfg = gates._cfg()["gate_3"]
    min_score, min_margin = cfg["min_template_score"], cfg["min_template_margin"]
    low = text.lower()
    matched = {a: sorted(k for k in kws if re.search(rf"\b{re.escape(k)}", low))
               for a, kws in ARCHETYPE_KEYWORDS.items()}
    scores = {a: sum(ARCHETYPE_KEYWORDS[a][k] for k in matched[a]) for a in ARCHETYPE_KEYWORDS}
    for a, pairs in (synonyms or {}).items():
        pairs = pairs[:MAX_SYNONYM_CREDIT]
        scores[a] += len(pairs)
        matched[a] = matched[a] + [f"{kw} (LLM synonym: '{ph}')" for ph, kw in pairs]
    ranked = sorted(scores, key=lambda a: -scores[a])
    best, second = ranked[0], ranked[1]
    margin = scores[best] - scores[second]
    if scores[best] < min_score:
        closest = (f"the closest, '{best}', scored {scores[best]} (matched {matched[best]})"
                   if scores[best] else "the idea matched no template keywords at all")
        reason = (f"No tested template fits this idea: {closest}; the minimum is {min_score}. "
                  f"Available templates: {', '.join(ARCHETYPE_KEYWORDS)}.")
        return {"archetype": None, "supported": False, "scores": scores, "matched": matched, "reason": reason}
    if margin < min_margin:
        reason = (f"Ambiguous idea: '{best}' ({scores[best]}, {matched[best]}) and '{second}' "
                  f"({scores[second]}, {matched[second]}) fit equally well, so no template is chosen.")
        return {"archetype": None, "supported": False, "scores": scores, "matched": matched, "reason": reason}
    reason = (f"'{best}' scored {scores[best]} (matched {matched[best]}), "
              f"{margin} ahead of '{second}' (min score {min_score}, min margin {min_margin}).")
    return {"archetype": best, "supported": True, "scores": scores, "matched": matched, "reason": reason}


def classify(text: str) -> tuple[str | None, dict[str, int]]:
    """(archetype or None when no template fits, scores)."""
    sel = select_template(text)
    return sel["archetype"], sel["scores"]


def _topic(brief: FounderBrief) -> str:
    stems = [k.strip() for kws in ARCHETYPE_KEYWORDS.values() for k in kws]
    kws = [k for k in evidence.keywords(brief.idea, 12)
           if k not in GENERIC and not any(st in k for st in stems)]
    if re.search(r"\bstem\b", brief.idea, re.I):
        return "STEM"
    return kws[0].title() if kws else "Starter"


def _clean(v: str) -> str:
    return "" if str(v).upper().startswith(("UNKNOWN", "ASSUMPTION")) else str(v)


# ---------------------------------------------------------------------------
# Deterministic, idea-derived sample content (labelled SAMPLE DATA)
# ---------------------------------------------------------------------------

_CARD_BANK = {
    "physics": [("Newton's second law", "F = m × a (force = mass × acceleration)", "Physics"),
                ("SI unit of electric charge", "Coulomb (C)", "Physics")],
    "math": [("Derivative of sin(x)", "cos(x)", "Calculus"),
             ("Quadratic formula", "x = (−b ± √(b² − 4ac)) / 2a", "Algebra")],
    "chemistry": [("Avogadro's number", "≈ 6.022 × 10²³ per mole", "Chemistry"),
                  ("pH of pure water at 25 °C", "7 (neutral)", "Chemistry")],
    "biology": [("Organelle that produces most ATP", "Mitochondrion", "Biology")],
    "programming": [("Time complexity of binary search", "O(log n)", "Computer science")],
    "arabic": [("Acceleration — Arabic term", "التسارع (at-tasāruʿ)", "Physics AR/EN"),
               ("Derivative — Arabic term", "المشتقة (al-mushtaqqa)", "Calculus AR/EN")],
    "study": [("What is spaced repetition?", "Reviewing material at increasing intervals to strengthen long-term memory",
               "Study skills")],
}


def _seeds(archetype: str, brief: FounderBrief, topic: str, ref_date: date | None = None) -> list[dict]:
    """ref_date: the 'today' that dated sample content is anchored to (replay: the capture date)."""
    low = f"{brief.idea} {brief.language}".lower()
    target = _clean(brief.target_user) or "users"
    if archetype == "spaced_repetition":
        keys = []
        if re.search(r"stem|science|engineering", low):
            keys += ["physics", "math", "chemistry", "biology"]
        for k in ("physics", "math", "chemistry", "biology", "programming"):
            if k in low and k not in keys:
                keys.append(k)
        if "arabic" in low:
            keys.append("arabic")
        keys = keys or ["study"]
        return [{"front": f, "back": b, "deck": d} for k in keys for f, b, d in _CARD_BANK[k]]
    if archetype == "booking":
        d0 = (ref_date or date.today()) + timedelta(days=7)
        return [{"title": f"{topic} 1:1 session", "provider": "Provider (sample)", "start": f"{d0}T10:00",
                 "duration_min": 45, "capacity": 1},
                {"title": f"{topic} group session", "provider": "Provider (sample)", "start": f"{d0}T14:00",
                 "duration_min": 90, "capacity": 8}]
    if archetype == "habit_tracker":
        return [{"name": f"{topic} practice", "target_per_week": 5, "unit": "sessions"},
                {"name": "Weekly reflection", "target_per_week": 1, "unit": "entries"}]
    if archetype == "directory":
        return [{"title": f"{topic} listing A (sample)", "category": topic, "location": _clean(brief.geography) or "Online",
                 "price": 0, "description": f"Sample listing for {target}."},
                {"title": f"{topic} listing B (sample)", "category": topic, "location": "Online",
                 "price": 10, "description": f"Second sample listing for {target}."}]
    return [{"title": f"Why {topic} matters for {target}", "module": 1, "position": 1, "minutes": 10,
             "body": "Sample lesson — replace with your content."},
            {"title": f"Getting started with {topic}", "module": 1, "position": 2, "minutes": 20,
             "body": "Sample lesson — replace with your content."},
            {"title": f"{topic} in practice: first project", "module": 2, "position": 1, "minutes": 30,
             "body": "Sample lesson — replace with your content."}]


def _features(archetype: str, canvas: LeanCanvas, critique: Critique) -> list[FeatureSpec]:
    problem = canvas.problem.content.split(" Evidence:")[0][:140]
    metric = "Key metric: " + canvas.key_metrics.content[:100]
    risk = critique.riskiest_assumptions[0].assumption if critique.riskiest_assumptions else "core demand"
    table = {
        "spaced_repetition": [("Due-today review queue", "Shows only the cards due today, oldest first.", problem, "due"),
                              ("SM-2 adaptive scheduling", "Grades 0–5 reschedule each card (1, 6, then ×ease days).", problem, "review"),
                              ("Retention stats", "Reviews, average ease and recall rate per user.", metric, "stats")],
        "booking": [("Live availability", "Remaining seats per session.", problem, "availability"),
                    ("Safe booking", "Capacity, duplicate and time-clash checks.", problem, "book"),
                    ("Self-service cancellation", "Frees the seat immediately.", metric, "cancel")],
        "habit_tracker": [("One-tap daily check-in", "Idempotent per day.", problem, "check_in"),
                          ("Streaks", "Consecutive-day streak, forgiving until end of day.", metric, "streak"),
                          ("Weekly targets", "Progress vs. weekly target per habit.", metric, "weekly_progress")],
        "directory": [("Ranked search with filters", "Title matches rank first; category/location/price filters.", problem, "search"),
                      ("Rate-limited inquiries", "Contact a listing owner; 3/day/listing anti-spam.", problem, "inquire"),
                      ("Category browsing", "Counts per category.", metric, "categories")],
        "course": [("Ordered lessons + next step", "Always shows the next unfinished lesson.", problem, "progress"),
                   ("Completion tracking", "Per-learner, idempotent completions.", metric, "complete"),
                   ("Completion certificate", "Issued only at 100%.", metric, "certificate")],
    }[archetype]
    feats = [FeatureSpec(name=n, description=d, traces_to=t, action=a) for n, d, t, a in table]
    feats.append(FeatureSpec(name="Consented waitlist (demand test)", description="Email + explicit consent; feeds the "
                             "pre-registered demand test. Nothing is sent automatically.",
                             traces_to=f"Riskiest assumption: {risk}", action="waitlist"))
    return feats


def _load_core(archetype: str):
    sys.path.insert(0, str(TEMPLATES / "_shared"))
    spec = importlib.util.spec_from_file_location(f"tpl_{archetype}", TEMPLATES / archetype / "core.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_spec(run_id: str, brief: FounderBrief, canvas: LeanCanvas, critique: Critique,
               use_llm: bool = True, selection: dict | None = None,
               ref_date: date | None = None) -> tuple[AppSpec, dict, str | None, int, dict]:
    selection = selection or select_template(_selection_text(brief, canvas))
    if not selection["supported"]:
        raise ValueError(selection["reason"])
    archetype, scores = selection["archetype"], selection["scores"]
    core = _load_core(archetype)
    topic = _topic(brief)
    langs = ["en"] + (["ar"] if "arabic" in brief.language.lower() else [])
    target = _clean(brief.target_user) or "early users"
    geo = _clean(brief.geography)
    spec = AppSpec(
        product_name=f"{topic} {SUFFIX[archetype]}",
        tagline=f"{TAGLINE[archetype]}, for {target}{' in ' + geo if geo else ''}.",
        archetype=archetype, item_label={"spaced_repetition": "Flashcard", "booking": "Session", "habit_tracker": "Habit",
                                         "directory": "Listing", "course": "Lesson"}[archetype],
        item_label_plural={"spaced_repetition": "Flashcards", "booking": "Sessions", "habit_tracker": "Habits",
                           "directory": "Listings", "course": "Lessons"}[archetype],
        fields=[FieldSpec(**f) for f in core.FIELDS],
        seed_items=_seeds(archetype, brief, topic, ref_date),
        features=_features(archetype, canvas, critique),
        languages=langs, free_tier_limit=200, target_user=target,
    )
    model, tokens = None, 0
    task = {"task": "spec_text", "mode": "not_used (rebuild attempt)", "model": None, "error": "", "applied": False}
    if use_llm:
        res = llm_gateway.complete_json(
            SPEC_PROMPT.read_text(encoding="utf-8"),
            f"Idea: {brief.idea}\nTarget user: {target}\nLanguage(s): {brief.language}\n"
            f"MVP type: {archetype}\nCurrent name: {spec.product_name}\nCurrent tagline: {spec.tagline}",
            SpecText, temperature=0.4, max_tokens=120)
        task.update(mode=res.mode, model=res.model, error=res.error)
        if res.live:
            problem = check_spec_text(res.value)
            if problem:
                # Schema-valid but unacceptable content: keep the deterministic text and say so.
                task.update(mode=llm_gateway.LLM_FALLBACK, model=None, error=f"rejected by code: {problem}")
            else:
                spec.product_name, spec.tagline = res.value.product_name.strip(), res.value.tagline.strip()
                model, tokens = res.model, res.tokens
                task["applied"] = True
    return spec, scores, model, tokens, task


_CODE_LIKE = re.compile(r"[<>{}`$\\]|https?://|www\.|\bimport\b|\bdef\b|;\s*$")


def check_spec_text(t) -> str:
    """Return a reason to reject LLM spec text, or '' if acceptable."""
    name, tag = t.product_name.strip(), t.tagline.strip()
    if not name or not tag:
        return "empty field"
    if len(name) > 40 or len(name.split()) > 5:
        return "product name too long"
    if len(tag) > 140:
        return "tagline too long"
    if _CODE_LIKE.search(name) or _CODE_LIKE.search(tag):
        return "code-like or URL content"
    found = gates.scan_output(f"{name} {tag}")
    return f"forbidden phrase {found}" if found else ""


def suggest_template(text: str, det: dict) -> tuple[dict, dict]:
    """LLM task 1. Only consulted when no template clears the threshold deterministically.
    Returns (final selection, task record)."""
    task = {"task": "template_suggestion", "mode": "not_needed (deterministic selection succeeded)",
            "model": None, "error": "", "accepted": [], "changed_selection": False}
    if det["supported"]:
        return det, task
    res = llm_gateway.complete_json(
        TEMPLATE_PROMPT.read_text(encoding="utf-8") + "\n\nTemplates and their keywords:\n"
        + json.dumps({a: sorted(k) for a, k in ARCHETYPE_KEYWORDS.items()}),
        f"Idea: {text}", TemplateSuggestion, temperature=0.0, max_tokens=200)
    task.update(mode=res.mode, model=res.model, error=res.error)
    if not res.live:
        return det, task
    accepted = accept_synonyms(text, res.value, det["matched"])
    task["accepted"] = [f"'{p}' -> {k} ({a})" for a, pairs in accepted.items() for p, k in pairs]
    if not accepted:
        return det, task
    final = select_template(text, accepted)
    task["changed_selection"] = final["archetype"] != det["archetype"]
    return final, task


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "feature"


def _spec_test(spec: AppSpec) -> str:
    feature_tests = []
    for f in spec.features:
        if f.action == "waitlist":
            body = ('        out = server.join_waitlist(store, {"email": "spec@example.com", "consent": True})\n'
                    '        self.assertEqual(out["status"], "joined")')
        else:
            body = ('        names = list(core.ACTION_EXAMPLES)\n'
                    f'        for name in names[:names.index("{f.action}") + 1]:  # earlier actions set up state\n'
                    '            params = dict(core.ACTION_EXAMPLES[name]["params"])\n'
                    '            params = {k: (first_id if v == "$first_id" else v) for k, v in params.items()}\n'
                    '            result = core.ACTIONS[name](store, params)\n'
                    '        self.assertIsInstance(result, dict)')
        feature_tests.append(
            f'    def test_feature_{_slug(f.name)}(self):\n'
            f'        """{f.name} - traces to: {f.traces_to[:80].replace(chr(34), chr(39))}"""\n'
            '        store, first_id = self._seeded()\n' + body + "\n")
    return f'''"""Idea-specific spec tests — GENERATED by HatchAI Phase 3 for "{spec.product_name}".

Each feature in the spec must map to an implemented action and run on the seeded data.
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import core  # noqa: E402
import server  # noqa: E402
from store import LimitError, Store  # noqa: E402

CONFIG = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))


class SpecTest(unittest.TestCase):
    def _seeded(self):
        store = Store()
        server.seed(store)
        return store, store.list()[0]["id"]

    def test_product_identity(self):
        self.assertEqual(CONFIG["product_name"], {json.dumps(spec.product_name, ensure_ascii=False)})
        self.assertEqual(CONFIG["archetype"], "{spec.archetype}")
        self.assertEqual(CONFIG["target_user"], {json.dumps(spec.target_user, ensure_ascii=False)})

    def test_config_fields_match_domain_model(self):
        self.assertEqual([f["name"] for f in CONFIG["fields"]], [f["name"] for f in core.FIELDS])

    def test_all_{len(spec.seed_items)}_seed_items_validate(self):
        self.assertEqual(len(CONFIG["seed_items"]), {len(spec.seed_items)})
        for item in CONFIG["seed_items"]:
            core.validate(dict(item))

    def test_every_feature_maps_to_an_implemented_action(self):
        for f in CONFIG["features"]:
            self.assertTrue(f["action"] == "waitlist" or f["action"] in core.ACTIONS, f["name"])
            self.assertTrue(f["traces_to"].strip(), f["name"] + " is not traced to a problem")

    def test_free_tier_limit_enforced(self):
        store = Store(item_limit=1)
        store.add(core.validate(dict(core.EXAMPLE_ITEM)))
        with self.assertRaises(LimitError):
            store.add(core.validate(dict(core.EXAMPLE_ITEM)))

{chr(10).join(feature_tests)}

if __name__ == "__main__":
    unittest.main()
'''


def render(run_id: str, spec: AppSpec) -> Path:
    out = GENERATED / run_id
    if out.exists():
        shutil.rmtree(out)
    (out / "tests").mkdir(parents=True)
    for name in ("server.py", "store.py", "index.html"):
        shutil.copy(TEMPLATES / "_shared" / name, out / name)
    shutil.copy(TEMPLATES / "_shared" / "test_server.py", out / "tests" / "test_server.py")
    shutil.copy(TEMPLATES / spec.archetype / "core.py", out / "core.py")
    shutil.copy(TEMPLATES / spec.archetype / "test_core.py", out / "tests" / "test_core.py")
    (out / "config.json").write_text(json.dumps({**spec.model_dump(), "seed_note": "SAMPLE DATA generated by HatchAI — "
                                                 "not real users or content.", "payments": "MOCKED"},
                                                indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "tests" / "test_spec.py").write_text(_spec_test(spec), encoding="utf-8")
    (out / "README.md").write_text(
        f"# {spec.product_name}\n\n{spec.tagline}\n\nGenerated by HatchAI Phase 3 (archetype `{spec.archetype}`). "
        "Python 3.10+ standard library only — no installs.\n\n```bash\npython server.py --port 8080   # open http://localhost:8080\n"
        "python -m unittest discover -s tests -v\n```\n\nSeed content is SAMPLE DATA. Payments are MOCKED.\n",
        encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def run_tests(app_dir: Path) -> dict:
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                          cwd=app_dir, capture_output=True, text=True, timeout=180,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = proc.stderr + proc.stdout
    m = re.search(r"Ran (\d+) tests?", out)
    ran = int(m.group(1)) if m else 0
    failed = int((re.search(r"failures=(\d+)", out) or [0, 0])[1])
    errors = int((re.search(r"errors=(\d+)", out) or [0, 0])[1])
    return {"ran": ran, "failed": failed, "errors": errors, "ok": proc.returncode == 0 and ran > 0,
            "seconds": round(time.time() - t0, 2), "output": out}


START_TIMEOUT_S = 30


def start_mvp_server(app_dir: Path, db: str, timeout: float = START_TIMEOUT_S):
    """Start a generated MVP on a port the OS picks (--port 0) and return (process, port).

    The server prints the port it actually bound, so there is no window in which another
    process can take a port we reserved and released. Raises RuntimeError if it does not
    report a port within `timeout` seconds; the process is stopped in that case.
    """
    import queue
    import threading
    proc = subprocess.Popen([sys.executable, "server.py", "--port", "0", "--db", db], cwd=app_dir,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(l) for l in proc.stdout], daemon=True).start()
    deadline, seen = time.time() + timeout, []
    while time.time() < deadline:
        try:
            line = lines.get(timeout=0.5)
        except queue.Empty:
            if proc.poll() is not None:
                break
            continue
        seen.append(line.strip())
        m = re.search(r"running on http://localhost:(\d+)", line)
        if m:
            return proc, int(m.group(1))
    proc.terminate()
    proc.wait(timeout=5)
    raise RuntimeError(f"MVP server did not report a port within {timeout:.0f} s; output: {seen[-3:]}")


def smoke(app_dir: Path) -> tuple[bool, str]:
    try:
        proc, port = start_mvp_server(app_dir, ":memory:")
    except RuntimeError as exc:
        return False, str(exc)
    try:
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                    health = json.loads(r.read())
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/items", timeout=2) as r:
                    items = json.loads(r.read())
                return True, f"server booted on :{port}; /health={health}; /api/items returned {len(items)} seeded items"
            except Exception:
                time.sleep(0.2)
        return False, "server reported a port but did not answer /health within 10 s"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def _log_llm_task(run_id: str, t: dict) -> None:
    """Every LLM task is logged with its explicit mode; `model` is set only when a model answered."""
    if not str(t["mode"]).startswith("LLM_"):
        return  # not consulted (e.g. deterministic selection succeeded); recorded in the spec only
    detail = t.get("error") or ("applied" if t.get("applied") else
                                f"accepted {t['accepted']}" if t.get("accepted") else "no effect")
    callbacks.log(run_id=run_id, agent="builder", action=f"llm_{t['task']}", sources=[],
                  model=t["model"] if t["mode"] == llm_gateway.LLM_LIVE else None, cost=0, phase=3,
                  outcome=f"{t['mode']}: {detail}"[:300])


def _selection_text(brief: FounderBrief, canvas: LeanCanvas) -> str:
    return f"{brief.idea} {canvas.solution.content}"


def unsupported_report(selection: dict, attempt: int, llm_tasks: list | None = None) -> dict:
    """Honest result when no tested template fits: nothing is generated, built or tested."""
    return {
        "llm_tasks": llm_tasks or [],
        "supported": False, "spec": None, "archetype_scores": selection["scores"],
        "template_matches": selection["matched"], "unsupported_reason": selection["reason"],
        "app_dir": None, "files": 0, "file_list": [],
        "tests": {"ran": 0, "failed": 0, "errors": 0, "ok": False, "seconds": 0,
                  "output": "NOT RUN: no MVP was generated."},
        "smoke_ok": False, "smoke_msg": "NOT RUN: no MVP was generated.", "attempt": attempt,
        "features_traced": False, "forbidden_phrases": [], "model": None,
    }


def run(run_id: str, brief: FounderBrief, canvas: LeanCanvas, critique: Critique, attempt: int = 1,
        ref_date: date | None = None) -> dict:
    text = _selection_text(brief, canvas)
    det = select_template(text)
    llm_tasks = []
    if attempt == 1:
        selection, t1 = suggest_template(text, det)
        llm_tasks.append(t1)
        _log_llm_task(run_id, t1)
    else:
        selection = det
    callbacks.log(run_id=run_id, agent="builder", action="select_template", sources=[], model=None, cost=0,
                  phase=3, outcome=selection["archetype"] or "unsupported")
    if not selection["supported"]:
        return unsupported_report(selection, attempt, llm_tasks)
    spec, scores, model, tokens, t2 = build_spec(run_id, brief, canvas, critique, use_llm=(attempt == 1),
                                                 selection=selection, ref_date=ref_date)
    llm_tasks.append(t2)
    _log_llm_task(run_id, t2)
    callbacks.log(run_id=run_id, agent="builder", action="design_app_spec", sources=[], model=None,
                  cost=0, phase=3)
    app_dir = render(run_id, spec)
    files = [p for p in app_dir.rglob("*") if p.is_file()]
    callbacks.log(run_id=run_id, agent="builder", action=f"generate_mvp_code_{spec.archetype}", sources=[],
                  model=None, cost=0, phase=3)
    tests = run_tests(app_dir)
    smoke_ok, smoke_msg = smoke(app_dir)
    callbacks.log(run_id=run_id, agent="builder", action="run_generated_tests", sources=[], model=None, cost=0,
                  phase=3, outcome=f"ran={tests['ran']} failed={tests['failed']} errors={tests['errors']} smoke={smoke_ok}")
    text_blob = json.dumps(spec.model_dump(), ensure_ascii=False)
    return {
        "llm_tasks": llm_tasks,
        "supported": True, "template_reason": selection["reason"],
        "spec": spec, "archetype_scores": scores, "app_dir": app_dir, "files": len(files),
        "file_list": sorted(str(p.relative_to(app_dir)).replace("\\", "/") for p in files),
        "tests": tests, "smoke_ok": smoke_ok, "smoke_msg": smoke_msg, "attempt": attempt,
        "features_traced": all(f.traces_to.strip() for f in spec.features),
        "forbidden_phrases": gates.scan_output(text_blob), "model": model,
    }
