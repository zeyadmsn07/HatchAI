"""Unit tests for SM-2 spaced repetition."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402
from store import Store  # noqa: E402


class SM2Test(unittest.TestCase):
    def setUp(self):
        self.s = Store()
        self.card = self.s.add(core.validate({"front": "F = ?", "back": "m * a"}))

    def test_intervals_grow_1_6_then_multiply(self):
        e, i, r = core.sm2(2.5, 0, 0, 5)
        self.assertEqual((i, r), (1, 1))
        e, i, r = core.sm2(e, i, r, 5)
        self.assertEqual((i, r), (6, 2))
        e2, i2, r2 = core.sm2(e, i, r, 5)
        self.assertEqual(i2, round(6 * e))
        self.assertGreater(e2, 2.5)

    def test_failed_recall_resets(self):
        e, i, r = core.sm2(2.6, 15, 4, 1)
        self.assertEqual((i, r), (1, 0))
        self.assertGreaterEqual(e, 1.3)

    def test_ease_never_below_floor(self):
        e = 1.3
        for _ in range(5):
            e, _, _ = core.sm2(e, 1, 0, 0)
        self.assertEqual(e, 1.3)

    def test_invalid_grade_rejected(self):
        with self.assertRaises(ValueError):
            core.sm2(2.5, 0, 0, 7)

    def test_review_moves_card_out_of_due_queue(self):
        today = "2026-01-10"
        self.s.update(self.card["id"], {**self.card, "due": today})
        self.assertEqual(core.due(self.s, {"today": today})["due_count"], 1)
        out = core.review(self.s, {"item_id": self.card["id"], "grade": 4, "today": today})
        self.assertEqual(out["due"], "2026-01-11")
        self.assertEqual(core.due(self.s, {"today": today})["due_count"], 0)
        self.assertEqual(core.stats(self.s, {})["reviews"], 1)

    def test_validation_requires_front_and_back(self):
        with self.assertRaises(ValueError):
            core.validate({"front": "only front"})


if __name__ == "__main__":
    unittest.main()
