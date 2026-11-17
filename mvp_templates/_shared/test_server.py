"""HTTP integration tests: boot the real server, create an item, run every action."""
import json
import os
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402
import server  # noqa: E402


def call(base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"null") if "json" in r.headers.get("Content-Type", "") else r.read()
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.base = server.serve_in_thread()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_health_and_ui(self):
        code, body = call(self.base, "/health")
        self.assertEqual(code, 200)
        self.assertEqual(body["product"], server.CONFIG["product_name"])
        code, html = call(self.base, "/")
        self.assertEqual(code, 200)
        self.assertIn(b"<script>", html)

    def test_seeded_items_are_served(self):
        code, items = call(self.base, "/api/items")
        self.assertEqual(code, 200)
        seeds = server.CONFIG["seed_items"]
        self.assertGreaterEqual(len(items), len(seeds))
        key = server.CONFIG["fields"][0]["name"]
        self.assertEqual([i[key] for i in items[:len(seeds)]], [s[key] for s in seeds])

    def test_create_item_and_reject_invalid(self):
        code, item = call(self.base, "/api/items", core.EXAMPLE_ITEM)
        self.assertEqual(code, 201)
        self.assertIn("id", item)
        code, err = call(self.base, "/api/items", {})
        self.assertEqual(code, 400)
        self.assertIn("error", err)

    def test_every_action_runs_over_http(self):
        _, items = call(self.base, "/api/items")
        first = items[0]["id"]
        for name, ex in core.ACTION_EXAMPLES.items():
            params = {k: (first if v == "$first_id" else v) for k, v in ex["params"].items()}
            code, body = call(self.base, f"/api/actions/{name}", params)
            self.assertEqual(code, 200, f"{name}: {body}")

    def test_waitlist_requires_consent_and_dedupes(self):
        code, _ = call(self.base, "/api/waitlist", {"email": "a@example.com"})
        self.assertEqual(code, 400)
        code, body = call(self.base, "/api/waitlist", {"email": "a@example.com", "consent": True})
        self.assertEqual((code, body["status"]), (201, "joined"))
        code, body = call(self.base, "/api/waitlist", {"email": "A@example.com", "consent": True})
        self.assertEqual(body["status"], "already_joined")
        code, body = call(self.base, "/api/waitlist/count")
        self.assertEqual(body["signups"], 1)

    def test_unknown_action_404(self):
        code, _ = call(self.base, "/api/actions/does_not_exist", {})
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
