"""Unit tests for booking capacity, duplicates, clashes and cancellation."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402
from store import Store  # noqa: E402


class BookingTest(unittest.TestCase):
    def setUp(self):
        self.s = Store()
        self.a = self.s.add(core.validate({"title": "A", "start": "2030-01-01T10:00", "duration_min": 60, "capacity": 1}))
        self.b = self.s.add(core.validate({"title": "B", "start": "2030-01-01T10:30", "duration_min": 60, "capacity": 5}))
        self.c = self.s.add(core.validate({"title": "C", "start": "2030-01-01T12:00", "duration_min": 30, "capacity": 5}))

    def test_capacity_enforced(self):
        core.book(self.s, {"item_id": self.a["id"], "client_name": "Mona"})
        with self.assertRaises(ValueError):
            core.book(self.s, {"item_id": self.a["id"], "client_name": "Omar"})

    def test_no_double_booking_same_client(self):
        core.book(self.s, {"item_id": self.b["id"], "client_name": "Mona"})
        with self.assertRaises(ValueError):
            core.book(self.s, {"item_id": self.b["id"], "client_name": "mona"})

    def test_clash_detection(self):
        core.book(self.s, {"item_id": self.a["id"], "client_name": "Mona"})
        with self.assertRaises(ValueError):
            core.book(self.s, {"item_id": self.b["id"], "client_name": "Mona"})
        core.book(self.s, {"item_id": self.c["id"], "client_name": "Mona"})  # no overlap

    def test_cancel_frees_seat(self):
        r = core.book(self.s, {"item_id": self.a["id"], "client_name": "Mona"})
        core.cancel(self.s, {"booking_id": r["booking_id"]})
        core.book(self.s, {"item_id": self.a["id"], "client_name": "Omar"})
        with self.assertRaises(ValueError):
            core.cancel(self.s, {"booking_id": r["booking_id"]})

    def test_availability_counts_seats(self):
        core.book(self.s, {"item_id": self.b["id"], "client_name": "Mona"})
        seats = {x["title"]: x["seats_left"] for x in core.availability(self.s, {})["sessions"]}
        self.assertEqual(seats["B"], 4)

    def test_validation(self):
        with self.assertRaises(ValueError):
            core.validate({"title": "X", "start": "not a date"})


if __name__ == "__main__":
    unittest.main()
