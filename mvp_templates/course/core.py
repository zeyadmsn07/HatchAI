"""Domain logic: self-paced course / learning path with progress and completion."""
from __future__ import annotations

import hashlib

FIELDS = [
    {"name": "title", "label": "Lesson title", "type": "text"},
    {"name": "module", "label": "Module number", "type": "number"},
    {"name": "position", "label": "Position in module", "type": "number"},
    {"name": "minutes", "label": "Minutes", "type": "number"},
    {"name": "body", "label": "Lesson content", "type": "longtext"},
]
EXAMPLE_ITEM = {"title": "Example lesson", "module": 9, "position": 1, "minutes": 5, "body": "Content"}


def validate(item: dict) -> dict:
    if not str(item.get("title", "")).strip():
        raise ValueError("'title' is required")
    item["module"] = int(item.get("module") or 1)
    item["position"] = int(item.get("position") or 1)
    item["minutes"] = int(item.get("minutes") or 10)
    if item["module"] < 1 or item["position"] < 1 or item["minutes"] < 1:
        raise ValueError("module, position and minutes must be positive")
    item.setdefault("body", "")
    return item


def _ordered(store):
    return sorted(store.list(), key=lambda l: (l["module"], l["position"], l["id"]))


def _done(store, learner) -> set[int]:
    return {e["item_id"] for e in store.events("completion") if e["learner"].lower() == learner.lower()}


def complete(store, params: dict) -> dict:
    lesson = store.get(params["item_id"])
    learner = str(params.get("learner", "")).strip()
    if not learner:
        raise ValueError("learner is required")
    if lesson["id"] in _done(store, learner):
        return {"lesson": lesson["title"], "status": "already_completed"}
    store.add_event("completion", lesson["id"], {"learner": learner})
    return {"lesson": lesson["title"], "status": "completed"}


def progress(store, params: dict) -> dict:
    learner = str(params.get("learner", "")).strip()
    lessons = _ordered(store)
    done = _done(store, learner)
    remaining = [l for l in lessons if l["id"] not in done]
    total_min = sum(l["minutes"] for l in lessons)
    done_min = sum(l["minutes"] for l in lessons if l["id"] in done)
    return {"learner": learner, "completed": len(lessons) - len(remaining), "total": len(lessons),
            "percent": round(100 * done_min / total_min) if total_min else 0,
            "next_lesson": remaining[0]["title"] if remaining else None,
            "minutes_left": total_min - done_min}


def certificate(store, params: dict) -> dict:
    p = progress(store, params)
    if p["total"] == 0 or p["completed"] < p["total"]:
        return {"eligible": False, "remaining_lessons": p["total"] - p["completed"]}
    cid = hashlib.sha256(f"{p['learner'].lower()}|{p['total']}".encode()).hexdigest()[:12]
    return {"eligible": True, "certificate_id": cid, "learner": p["learner"]}


ACTIONS = {"complete": complete, "progress": progress, "certificate": certificate}
ACTION_EXAMPLES = {
    "complete": {"label": "Mark lesson complete", "params": {"item_id": "$first_id", "learner": "demo"}},
    "progress": {"label": "My progress", "params": {"learner": "demo"}},
    "certificate": {"label": "Completion certificate", "params": {"learner": "demo"}},
}
