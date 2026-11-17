"""Unit tests for directory search ranking, filters and inquiry rate limits."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402
from store import Store  # noqa: E402


class DirectoryTest(unittest.TestCase):
    def setUp(self):
        self.s = Store()
        add = lambda **k: self.s.add(core.validate(k))
        self.a = add(title="Python tutor", category="Tutoring", location="Cairo", price=10, description="python lessons")
        self.b = add(title="Design mentor", category="Mentoring", location="Online", price=0, description="python and figma")
        self.c = add(title="Math tutor", category="Tutoring", location="Giza", price=30, description="algebra")

    def test_title_matches_rank_first(self):
        r = core.search(self.s, {"q": "python"})
        self.assertEqual([x["title"] for x in r["results"]], ["Python tutor", "Design mentor"])

    def test_filters(self):
        self.assertEqual(core.search(self.s, {"category": "tutoring"})["count"], 2)
        self.assertEqual(core.search(self.s, {"max_price": 15})["count"], 2)
        self.assertEqual(core.search(self.s, {"location": "giza"})["results"][0]["title"], "Math tutor")

    def test_inquiry_rate_limited(self):
        for _ in range(core.MAX_INQUIRIES_PER_DAY):
            core.inquire(self.s, {"item_id": self.a["id"], "name": "Ali", "message": "hi"})
        with self.assertRaises(ValueError):
            core.inquire(self.s, {"item_id": self.a["id"], "name": "ali", "message": "hi again"})

    def test_inquiry_requires_message(self):
        with self.assertRaises(ValueError):
            core.inquire(self.s, {"item_id": self.a["id"], "name": "Ali", "message": " "})

    def test_categories_and_validation(self):
        self.assertEqual(core.categories(self.s, {})["categories"]["Tutoring"], 2)
        with self.assertRaises(ValueError):
            core.validate({"title": "x", "price": -1})


if __name__ == "__main__":
    unittest.main()
