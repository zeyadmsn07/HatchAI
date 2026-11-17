"""Domain logic: habit / routine tracker with streaks and weekly targets."""
from __future__ import annotations

from datetime import date, timedelta

FIELDS = [
    {"name": "name", "label": "Habit / routine", "type": "text"},
    {"name": "target_per_week", "label": "Target check-ins per week", "type": "number"},
    {"name": "unit", "label": "Unit (e.g. minutes, pages)", "type": "text"},
]
EXAMPLE_ITEM = {"name": "Example habit", "target_per_week": 3, "unit": "sessions"}


def _today(params) -> date:
    t = params.get("today") or params.get("date")
    return date.fromisoformat(t) if t else date.today()


def validate(item: dict) -> dict:
    if not str(item.get("name", "")).strip():
        raise ValueError("'name' is required")
    t = int(item.get("target_per_week") or 3)
    if not 1 <= t <= 7 * 5:
        raise ValueError("target_per_week must be between 1 and 35")
    item["target_per_week"] = t
    item.setdefault("unit", "sessions")
    return item


def _days(store, item_id) -> set[str]:
    return {e["date"] for e in store.events("checkin", item_id)}


def check_in(store, params: dict) -> dict:
    habit = store.get(params["item_id"])
    day = _today(params).isoformat()
    if day in _days(store, habit["id"]):
        return {"item_id": habit["id"], "date": day, "status": "already_checked_in"}
    store.add_event("checkin", habit["id"], {"date": day, "amount": float(params.get("amount") or 1)})
    return {"item_id": habit["id"], "date": day, "status": "checked_in"}


def streak(store, params: dict) -> dict:
    habit = store.get(params["item_id"])
    days = _days(store, habit["id"])
    d = _today(params)
    if d.isoformat() not in days:
        d -= timedelta(days=1)  # streak still alive if yesterday was done
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return {"item_id": habit["id"], "streak_days": n}


def weekly_progress(store, params: dict) -> dict:
    today = _today(params)
    start = today - timedelta(days=6)
    out = []
    for h in store.list():
        done = sum(1 for d in _days(store, h["id"]) if start.isoformat() <= d <= today.isoformat())
        out.append({"id": h["id"], "name": h["name"], "done": done, "target": h["target_per_week"],
                    "on_track": done >= h["target_per_week"]})
    return {"week_ending": today.isoformat(), "habits": out}


ACTIONS = {"check_in": check_in, "streak": streak, "weekly_progress": weekly_progress}
ACTION_EXAMPLES = {
    "check_in": {"label": "Check in today", "params": {"item_id": "$first_id"}},
    "streak": {"label": "Current streak", "params": {"item_id": "$first_id"}},
    "weekly_progress": {"label": "Weekly progress", "params": {}},
}
