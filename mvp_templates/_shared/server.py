"""HTTP server for the generated MVP (standard library only).

    python server.py --port 8080 --db app.db

Routes:
  GET  /                    web UI
  GET  /health              health check
  GET  /api/config          product config (fields, features, actions)
  GET  /api/items           list items
  POST /api/items           create item (validated by core.validate)
  POST /api/actions/<name>  run a domain action from core.ACTIONS
  POST /api/waitlist        demand-test sign-up (email + explicit consent; nothing is sent)
  GET  /api/waitlist/count  number of sign-ups (read by HatchAI Phase 6)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import core
from store import LimitError, Store

HERE = pathlib.Path(__file__).parent
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))


def seed(store: Store) -> None:
    if store.count() == 0:
        for item in CONFIG.get("seed_items", []):
            store.add(core.validate(dict(item)))


EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def join_waitlist(store: Store, body: dict) -> dict:
    email = str(body.get("email", "")).strip().lower()
    if not EMAIL.match(email):
        raise ValueError("a valid email is required")
    if body.get("consent") is not True:
        raise ValueError("explicit consent is required")
    if any(e["email"] == email for e in store.events("waitlist")):
        return {"status": "already_joined"}
    store.add_event("waitlist", None, {"email": email})
    return {"status": "joined"}


def make_handler(store: Store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep test output quiet
            pass

        def _send(self, code: int, body, ctype="application/json"):
            raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 100_000:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html")
            if self.path == "/health":
                return self._send(200, {"status": "ok", "product": CONFIG["product_name"]})
            if self.path == "/api/config":
                return self._send(200, {**CONFIG, "actions": core.ACTION_EXAMPLES})
            if self.path == "/api/items":
                return self._send(200, store.list())
            if self.path == "/api/waitlist/count":
                return self._send(200, {"signups": len(store.events("waitlist"))})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            try:
                body = self._body()
                if self.path == "/api/items":
                    return self._send(201, store.add(core.validate(body)))
                if self.path == "/api/waitlist":
                    return self._send(201, join_waitlist(store, body))
                if self.path.startswith("/api/actions/"):
                    name = self.path.rsplit("/", 1)[-1]
                    if name not in core.ACTIONS:
                        return self._send(404, {"error": f"unknown action {name}"})
                    return self._send(200, core.ACTIONS[name](store, body))
                return self._send(404, {"error": "not found"})
            except LimitError as exc:
                return self._send(402, {"error": str(exc)})
            except (ValueError, KeyError, TypeError) as exc:
                return self._send(400, {"error": str(exc)})

    return Handler


def make_server(port: int = 0, db_path: str = ":memory:") -> ThreadingHTTPServer:
    store = Store(db_path, item_limit=int(CONFIG.get("free_tier_limit", 0)))
    seed(store)
    return ThreadingHTTPServer(("127.0.0.1" if port == 0 else "0.0.0.0", port), make_handler(store))


def serve_in_thread(db_path: str = ":memory:"):
    srv = make_server(0, db_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--db", default="app.db")
    a = ap.parse_args()
    srv = make_server(a.port, a.db)
    print(f"{CONFIG['product_name']} running on http://localhost:{a.port}")
    srv.serve_forever()
