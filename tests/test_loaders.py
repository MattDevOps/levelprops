"""Offline tests for the shared session builder used by CSV + live feeds."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from levelprobs.model import Bar, BARS_PER_RTH
from levelprobs.loaders import sessions_from_pairs, _et


def _rth_pairs(day_iso, n_bars):
    """n_bars contiguous 5-min RTH bars from 09:30 ET on the given day.

    The loader expects ET-stamped datetimes, so build them directly in ET.
    """
    start = _et(datetime.fromisoformat(f"{day_iso}T12:00:00+00:00")) \
        .replace(hour=9, minute=30, second=0, microsecond=0)
    out = []
    for i in range(n_bars):
        ts = start + timedelta(minutes=5 * i)
        px = 100.0 + i
        out.append((ts, Bar(px, px + 1, px - 1, px + 0.5)))
    return out


class SessionsFromPairs(unittest.TestCase):
    def test_full_day_kept(self):
        sess = sessions_from_pairs(_rth_pairs("2026-06-01", BARS_PER_RTH), warn=False)
        self.assertEqual(len(sess), 1)
        self.assertEqual(len(sess[0].bars), BARS_PER_RTH)

    def test_partial_day_skipped_when_require_full(self):
        with self.assertRaises(ValueError):           # only a partial day -> none usable
            sessions_from_pairs(_rth_pairs("2026-06-01", 10), warn=False,
                                require_full=True)

    def test_partial_day_kept_when_not_require_full(self):
        sess = sessions_from_pairs(_rth_pairs("2026-06-01", 10), warn=False,
                                   require_full=False)
        self.assertEqual(len(sess), 1)
        self.assertEqual(len(sess[0].bars), 10)       # the still-forming live session

    def test_prior_close_chains_across_days(self):
        pairs = _rth_pairs("2026-06-01", BARS_PER_RTH) + \
            _rth_pairs("2026-06-02", BARS_PER_RTH)
        sess = sessions_from_pairs(pairs, warn=False)
        self.assertEqual(len(sess), 2)
        self.assertEqual(sess[1].prior_close, sess[0].rth_close)


if __name__ == "__main__":
    unittest.main()
