import unittest
import sys
from pathlib import Path
from datetime import date, datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mkd_coverage_audit import assess_coverage


class CoverageAuditTests(unittest.TestCase):
    def test_missing_sessions_do_not_become_fabricated_bars(self):
        report = assess_coverage([(date(2026, 11, 16), 263, 263),
                                  (date(2026, 11, 18), 144, 144)],
                                 as_of=date(2026, 11, 22), expected_min=250)
        self.assertEqual(report["latest_session"], "2026-11-18")
        self.assertTrue(report["sessions"][-1]["below_expected_min"])
        self.assertFalse(report["paper_authorized"])
        self.assertFalse(report["pit_verified"])

    def test_empty_never_ready(self):
        self.assertFalse(assess_coverage([], as_of=date(2026, 11, 22))["has_recent_coverage"])

    def test_duplicate_day_rejected(self):
        with self.assertRaises(ValueError):
            assess_coverage([(date(2026, 11, 18), 1, 1),
                             (date(2026, 11, 18), 1, 1)], as_of=date(2026, 11, 22))

    def test_future_session_rejected(self):
        with self.assertRaises(ValueError):
            assess_coverage([(date(2026, 11, 23), 1, 1)], as_of=date(2026, 11, 22))

    def test_invalid_counts_rejected(self):
        with self.assertRaises(ValueError):
            assess_coverage([(date(2026, 11, 18), 3, 2)], as_of=date(2026, 11, 22))
        with self.assertRaises(ValueError):
            assess_coverage([(date(2026, 11, 18), True, 2)], as_of=date(2026, 11, 22))

    def test_invalid_as_of_rejected(self):
        with self.assertRaises(ValueError):
            assess_coverage([], as_of=datetime(2026, 11, 22))


if __name__ == "__main__":
    unittest.main()
