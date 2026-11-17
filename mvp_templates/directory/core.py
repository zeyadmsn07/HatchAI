"""Domain logic: searchable directory / listings with rate-limited inquiries."""
from __future__ import annotations

import re
from datetime import datetime, timezone

FIELDS = [
    {"name": "title", "label": "Title", "type": "text"},
    {"name": "category", "label": "Category", "type": "text"},
    {"name": "location", "label": "Location", "type": "text"},
    {"name": "price", "label": "Price (0 = free)", "type": "number"},
    {"name": "description", "label": "Description", "type": "longtext"},
]
EXAMPLE_ITEM = {"title": "Example listing", "category": "General", "location": "Online", "price": 0,
                "description": "An example listing"}
MAX_INQUIRIES_PER_DAY = 3


def validate(item: dict) -> dict:
    if not str(item.get("title", "")).strip():
        raise ValueError("'title' is required")
    price = float(item.get("price") or 0)
    if price < 0:
        raise ValueError("price cannot be negative")
    item["price"] = price
    for f in ("category", "location", "description"):
        item[f] = str(item.get(f, "")).strip()
    return item


def _tokens(s: str) -> list[str]:
    return re.findall(r"\w+", s.lower())


def search(store, params: dict) -> dict:
    q = _tokens(str(params.get("q", "")))
    cat = str(params.get("category", "")).lower()
    loc = str(params.get("location", "")).lower()
    max_price = params.get("max_price")
    hits = []
    for it in store.list():
        if cat and it["category"].lower() != cat:
            continue
        if loc and loc not in it["location"].lower():
            continue
        if max_price not in (None, "") and it["price"] > float(max_price):
            continue
        title, body = _tokens(it["title"]), _tokens(it["description"] + " " + it["category"])
        score = sum(3 * title.count(t) + body.count(t) for t in q) if q else 1
        if score > 0:
            hits.append((score, it))
    hits.sort(key=lambda x: (-x[0], x[1]["price"], x[1]["id"]))
    return {"count": len(hits), "results": [{"score": s, **it} for s, it in hits[:20]]}


def inquire(store, params: dict) -> dict:
    listing = store.get(params["item_id"])
    name = str(params.get("name", "")).strip()
    msg = str(params.get("message", "")).strip()
    if not name or not msg:
        raise ValueError("name and message are required")
    today = datetime.now(timezone.utc).date().isoformat()
    recent = [e for e in store.events("inquiry", listing["id"]) if e["name"].lower() == name.lower() and e["day"] == today]
    if len(recent) >= MAX_INQUIRIES_PER_DAY:
        raise ValueError("too many inquiries today for this listing")
    ev = store.add_event("inquiry", listing["id"], {"name": name, "message": msg[:1000], "day": today})
    return {"inquiry_id": ev["id"], "listing": listing["title"], "status": "sent_to_owner_inbox"}


def categories(store, params: dict) -> dict:
    out: dict[str, int] = {}
    for it in store.list():
        out[it["category"] or "Uncategorised"] = out.get(it["category"] or "Uncategorised", 0) + 1
    return {"categories": out}


ACTIONS = {"search": search, "inquire": inquire, "categories": categories}
ACTION_EXAMPLES = {
    "search": {"label": "Search", "params": {"q": "", "category": "", "location": "", "max_price": ""}},
    "inquire": {"label": "Send inquiry", "params": {"item_id": "$first_id", "name": "Demo user", "message": "Is this available?"}},
    "categories": {"label": "Browse categories", "params": {}},
}
