"""Sanity properties the engine must satisfy. Run: python3 -m pytest -q
(or: python3 tests/test_engine.py for a stdlib unittest run)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from levelprobs.instruments import get_instrument
from levelprobs.synth import generate_sessions
from levelprobs.engine import (touch_probability, first_break_stats,
                               current_atr, make_weight_fn)


# Module-level, NOT a class attribute: a plain function stored on a class binds
# as a method on instance access (WF would pass `self` as a sneaky 2nd arg).
WF = make_weight_fn(252)


class EngineProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inst = get_instrument("ES")
        cls.sessions = generate_sessions(inst, 600, date(2026, 6, 5), seed=7)
        cls.atr = current_atr(cls.sessions)
        cls.wf = WF

    def test_zero_distance_is_certain(self):
        self.assertEqual(touch_probability(self.sessions, 10, 0.0, "up", self.atr), 1.0)

    def test_prob_in_unit_interval(self):
        p = touch_probability(self.sessions, 10, 50.0, "up", self.atr, WF)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

    def test_farther_is_less_likely(self):
        near = touch_probability(self.sessions, 10, 20.0, "up", self.atr, WF)
        far = touch_probability(self.sessions, 10, 120.0, "up", self.atr, WF)
        self.assertGreaterEqual(near, far)

    def test_less_time_left_is_less_likely(self):
        early = touch_probability(self.sessions, 5, 60.0, "up", self.atr, WF)
        late = touch_probability(self.sessions, 70, 60.0, "up", self.atr, WF)
        self.assertGreaterEqual(early, late)

    def test_first_break_probabilities_sum_to_one(self):
        b = first_break_stats(self.sessions, window=252, weight_fn=WF)
        total = b["broke_high"] + b["broke_low"] + b["neither"]
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_recency_weighting_changes_estimate(self):
        flat = first_break_stats(self.sessions, 600, make_weight_fn(10_000_000))
        recent = first_break_stats(self.sessions, 600, make_weight_fn(60))
        # not asserting direction, just that recency weighting actually moves it
        self.assertNotAlmostEqual(flat["broke_high"], recent["broke_high"], places=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
