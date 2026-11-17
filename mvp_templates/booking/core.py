"""Domain logic: bookable sessions with capacity and clash detection."""
from __future__ import annotations

from datetime import datetime, timedelta

FIELDS = [
    {"name": "title", "label": "Session title", "type": "text"},
    {"name": "provider", "label": "Provider", "type": "text"},
    {"name": "start", "label": "Start (YYYY-MM-DDTHH:MM)", "type": "datetime"},
    {"name": "duration_min", "label": "Duration (minutes)", "type": "number"},
    {"name": "capacity", "label": "Seats", "type": "number"},
]
EXAMPLE_ITEM = {"title": "Example session", "provider": "Host", "start": "2030-01-01T10:00",
                "duration_min": 60, "capacity": 2}


def validate(item: dict) -> dict:
    if not str(item.get("title", "")).strip():
        raise ValueError("'title' is required")
    try:
        datetime.fromisoformat(str(item.get("start")))
    except ValueError:
        raise ValueError("'start' must be an ISO datetime like 2030-01-01T10:00")
    item["duration_min"] = int(item.get("duration_min") or 60)
    item["capacity"] = int(item.get("capacity") or 1)
    if item["duration_min"] <= 0 or item["capacity"] <= 0:
        raise ValueError("duration and capacity must be positive")
    item.setdefault("provider", "")
    return item


def _window(slot):
    s = datetime.fromisoformat(slot["start"])
    return s, s + timedelta(minutes=int(slot["duration_min"]))


def _active(store, slot_id=None):
    return [b for b in store.events("booking", slot_id) if b["status"] == "active"]


def book(store, params: dict) -> dict:
    slot = store.get(params["item_id"])
    client = str(params.get("client_name", "")).strip()
    if not client:
        raise ValueError("client_name is required")
    active = _active(store, slot["id"])
    if any(b["client_name"].lower() == client.lower() for b in active):
        raise ValueError(f"{client} already booked this session")
    if len(active) >= slot["capacity"]:
        raise ValueError("session is full")
    s0, e0 = _window(slot)
    for b in _active(store):
        other = store.get(b["item_id"])
        if b["client_name"].lower() == client.lower() and other["id"] != slot["id"]:
            s1, e1 = _window(other)
            if s0 < e1 and s1 < e0:
                raise ValueError(f"{client} has a clashing booking: {other['title']}")
    ev = store.add_event("booking", slot["id"], {"client_name": client, "status": "active"})
    return {"booking_id": ev["id"], "slot": slot["title"], "seats_left": slot["capacity"] - len(active) - 1}


def cancel(store, params: dict) -> dict:
    bid = int(params["booking_id"])
    for b in store.events("booking"):
        if b["id"] == bid:
            if b["status"] != "active":
                raise ValueError("booking already cancelled")
            store.update_event(bid, {"client_name": b["client_name"], "status": "cancelled"})
            return {"booking_id": bid, "status": "cancelled"}
    raise KeyError(f"booking {bid} not found")


def availability(store, params: dict) -> dict:
    day = params.get("date") or ""
    out = []
    for slot in store.list():
        if day and not slot["start"].startswith(day):
            continue
        out.append({"id": slot["id"], "title": slot["title"], "start": slot["start"],
                    "seats_left": slot["capacity"] - len(_active(store, slot["id"]))})
    return {"sessions": sorted(out, key=lambda x: x["start"])}


ACTIONS = {"availability": availability, "book": book, "cancel": cancel}
ACTION_EXAMPLES = {
    "availability": {"label": "Show availability", "params": {"date": ""}},
    "book": {"label": "Book a seat", "params": {"item_id": "$first_id", "client_name": "Demo client"}},
    "cancel": {"label": "Cancel booking", "params": {"booking_id": 1}},
}
