"""Domain logic: spaced-repetition flashcards (SM-2 scheduling)."""
from __future__ import annotations

from datetime import date, timedelta

FIELDS = [
    {"name": "front", "label": "Front (question)", "type": "text"},
    {"name": "back", "label": "Back (answer)", "type": "longtext"},
    {"name": "deck", "label": "Deck / subject", "type": "text"},
]
EXAMPLE_ITEM = {"front": "Example question", "back": "Example answer", "deck": "General"}


def _today(params) -> date:
    t = params.get("today")
    return date.fromisoformat(t) if t else date.today()


def validate(item: dict) -> dict:
    for f in ("front", "back"):
        if not str(item.get(f, "")).strip():
            raise ValueError(f"'{f}' is required")
    item.setdefault("deck", "General")
    item.setdefault("ease", 2.5)
    item.setdefault("interval", 0)
    item.setdefault("reps", 0)
    item.setdefault("due", date.today().isoformat())
    return item


def sm2(ease: float, interval: int, reps: int, grade: int) -> tuple[float, int, int]:
    """Classic SM-2. grade 0..5; returns (ease, interval_days, reps)."""
    if not 0 <= grade <= 5:
        raise ValueError("grade must be 0..5")
    if grade < 3:
        reps, interval = 0, 1
    else:
        interval = 1 if reps == 0 else 6 if reps == 1 else round(interval * ease)
        reps += 1
    ease = max(1.3, ease + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    return round(ease, 3), interval, reps


def review(store, params: dict) -> dict:
    card = store.get(params["item_id"])
    grade = int(params.get("grade", 4))
    ease, interval, reps = sm2(float(card["ease"]), int(card["interval"]), int(card["reps"]), grade)
    card.update(ease=ease, interval=interval, reps=reps, due=(_today(params) + timedelta(days=interval)).isoformat())
    store.update(card["id"], card)
    store.add_event("review", card["id"], {"grade": grade, "interval": interval})
    return card


def due(store, params: dict) -> dict:
    today = _today(params).isoformat()
    deck = params.get("deck") or None
    cards = [c for c in store.list() if c["due"] <= today and (deck is None or c["deck"] == deck)]
    cards.sort(key=lambda c: (c["due"], c["id"]))
    limit = int(params.get("limit") or 20)
    return {"today": today, "due_count": len(cards), "cards": cards[:limit]}


def stats(store, params: dict) -> dict:
    cards = store.list()
    reviews = store.events("review")
    decks: dict[str, int] = {}
    for c in cards:
        decks[c["deck"]] = decks.get(c["deck"], 0) + 1
    return {"cards": len(cards), "reviews": len(reviews), "decks": decks,
            "avg_ease": round(sum(c["ease"] for c in cards) / len(cards), 2) if cards else None,
            "retention_rate": round(sum(1 for r in reviews if r["grade"] >= 3) / len(reviews), 2) if reviews else None}


ACTIONS = {"due": due, "review": review, "stats": stats}
ACTION_EXAMPLES = {
    "due": {"label": "Cards due today", "params": {"deck": ""}},
    "review": {"label": "Review a card", "params": {"item_id": "$first_id", "grade": 4}},
    "stats": {"label": "Study stats", "params": {}},
}
