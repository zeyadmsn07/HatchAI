"""Unit tests for check-ins, streaks and weekly targets."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402
from store import Store  # noqa: E402


class HabitTest(unittest.TestCase):
    def setUp(self):
        self.s = Store()
        self.h = self.s.add(core.validate({"name": "Read", "target_per_week": 3}))

    def _ci(self, day):
        return core.check_in(self.s, {"item_id": self.h["id"], "date": day})

    def test_check_in_is_idempotent_per_day(self):
        self.assertEqual(self._ci("2030-01-05")["status"], "checked_in")
        self.assertEqual(self._ci("2030-01-05")["status"], "already_checked_in")

    def test_streak_counts_consecutive_days(self):
        for d in ("2030-01-01", "2030-01-02", "2030-01-03", "2030-01-05"):
            self._ci(d)
        self.assertEqual(core.streak(self.s, {"item_id": self.h["id"], "today": "2030-01-05"})["streak_days"], 1)
        self.assertEqual(core.streak(self.s, {"item_id": self.h["id"], "today": "2030-01-04"})["streak_days"], 3)

    def test_streak_broken_after_gap(self):
        self._ci("2030-01-01")
        self.assertEqual(core.streak(self.s, {"item_id": self.h["id"], "today": "2030-01-03"})["streak_days"], 0)

    def test_weekly_progress_on_track(self):
        for d in ("2030-01-01", "2030-01-02", "2030-01-03"):
            self._ci(d)
        h = core.weekly_progress(self.s, {"today": "2030-01-04"})["habits"][0]
        self.assertEqual((h["done"], h["on_track"]), (3, True))
        h = core.weekly_progress(self.s, {"today": "2030-01-09"})["habits"][0]
        self.assertFalse(h["on_track"])

    def test_validation(self):
        with self.assertRaises(ValueError):
            core.validate({"name": ""})
        with self.assertRaises(ValueError):
            core.validate({"name": "x", "target_per_week": 99})


if __name__ == "__main__":
    unittest.main()
