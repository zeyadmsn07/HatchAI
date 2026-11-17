"""SQLite store for the generated MVP (standard library only)."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone


class LimitError(ValueError):
    pass


class Store:
    def __init__(self, path: str = ":memory:", item_limit: int = 0):
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.item_limit = item_limit
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, created_at TEXT);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                item_id INTEGER, data TEXT NOT NULL, created_at TEXT);
        """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # items -------------------------------------------------------------
    def add(self, data: dict) -> dict:
        with self._lock:
            if self.item_limit and self.count() >= self.item_limit:
                raise LimitError(f"Free tier holds {self.item_limit} items (paid tier is MOCKED).")
            cur = self.conn.execute("INSERT INTO items (data, created_at) VALUES (?, ?)",
                                    (json.dumps(data, ensure_ascii=False), self._now()))
            self.conn.commit()
            return {"id": cur.lastrowid, **data}

    def get(self, item_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM items WHERE id=?", (int(item_id),)).fetchone()
        if not row:
            raise KeyError(f"item {item_id} not found")
        return {"id": row["id"], **json.loads(row["data"])}

    def update(self, item_id: int, data: dict) -> dict:
        data = {k: v for k, v in data.items() if k != "id"}
        with self._lock:
            self.conn.execute("UPDATE items SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), int(item_id)))
            self.conn.commit()
        return {"id": int(item_id), **data}

    def list(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM items ORDER BY id").fetchall()
        return [{"id": r["id"], **json.loads(r["data"])} for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    # events ------------------------------------------------------------
    def add_event(self, kind: str, item_id: int | None, data: dict) -> dict:
        with self._lock:
            cur = self.conn.execute("INSERT INTO events (kind, item_id, data, created_at) VALUES (?, ?, ?, ?)",
                                    (kind, item_id, json.dumps(data, ensure_ascii=False), self._now()))
            self.conn.commit()
            return {"id": cur.lastrowid, "kind": kind, "item_id": item_id, **data}

    def update_event(self, event_id: int, data: dict) -> None:
        with self._lock:
            self.conn.execute("UPDATE events SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), int(event_id)))
            self.conn.commit()

    def metrics(self) -> dict:
        """Demand-test counts, with REAL and TEST traffic always kept apart.

        Events without a traffic label (older databases) count as real.
        """
        out = {t: {"visits": 0, "unique_visitors": 0, "signups": 0} for t in ("real", "test")}
        visitors: dict[str, set] = {"real": set(), "test": set()}
        for e in self.events("visit"):
            t = "test" if e.get("traffic") == "test" else "real"
            out[t]["visits"] += 1
            visitors[t].add(e.get("visitor"))
        for t, ids in visitors.items():
            out[t]["unique_visitors"] = len(ids)
        for e in self.events("waitlist"):
            out["test" if e.get("traffic") == "test" else "real"]["signups"] += 1
        return out

    def events(self, kind: str, item_id: int | None = None) -> list[dict]:
        if item_id is None:
            rows = self.conn.execute("SELECT * FROM events WHERE kind=? ORDER BY id", (kind,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM events WHERE kind=? AND item_id=? ORDER BY id",
                                     (kind, int(item_id))).fetchall()
        return [{"id": r["id"], "item_id": r["item_id"], **json.loads(r["data"])} for r in rows]
