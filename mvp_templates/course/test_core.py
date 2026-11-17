"""Unit tests for lesson ordering, progress and certificates."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402
from store import Store  # noqa: E402


class CourseTest(unittest.TestCase):
    def setUp(self):
        self.s = Store()
        add = lambda **k: self.s.add(core.validate(k))
        self.l2 = add(title="Two", module=1, position=2, minutes=30)
        self.l1 = add(title="One", module=1, position=1, minutes=10)
        self.l3 = add(title="Three", module=2, position=1, minutes=60)

    def test_next_lesson_follows_module_order(self):
        self.assertEqual(core.progress(self.s, {"learner": "sara"})["next_lesson"], "One")
        core.complete(self.s, {"item_id": self.l1["id"], "learner": "sara"})
        self.assertEqual(core.progress(self.s, {"learner": "sara"})["next_lesson"], "Two")

    def test_percent_weighted_by_minutes(self):
        core.complete(self.s, {"item_id": self.l3["id"], "learner": "sara"})
        p = core.progress(self.s, {"learner": "sara"})
        self.assertEqual((p["percent"], p["minutes_left"]), (60, 40))

    def test_completion_idempotent_and_per_learner(self):
        core.complete(self.s, {"item_id": self.l1["id"], "learner": "sara"})
        self.assertEqual(core.complete(self.s, {"item_id": self.l1["id"], "learner": "Sara"})["status"], "already_completed")
        self.assertEqual(core.progress(self.s, {"learner": "omar"})["completed"], 0)

    def test_certificate_only_when_finished(self):
        self.assertFalse(core.certificate(self.s, {"learner": "sara"})["eligible"])
        for l in (self.l1, self.l2, self.l3):
            core.complete(self.s, {"item_id": l["id"], "learner": "sara"})
        cert = core.certificate(self.s, {"learner": "sara"})
        self.assertTrue(cert["eligible"])
        self.assertEqual(len(cert["certificate_id"]), 12)

    def test_validation(self):
        with self.assertRaises(ValueError):
            core.validate({"title": "x", "minutes": -5})
        with self.assertRaises(ValueError):
            core.complete(self.s, {"item_id": self.l1["id"], "learner": ""})


if __name__ == "__main__":
    unittest.main()
