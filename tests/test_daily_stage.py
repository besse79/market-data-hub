from datetime import datetime, timezone
import unittest
from src.daily_stage import stage_batch

NOW = datetime(2026, 11, 21, 10, tzinfo=timezone.utc)
BAR = {"session_date":"2026-11-20","open":10,"high":11,"low":9,"close":10.5,"volume":100}

class DailyStageTests(unittest.TestCase):
    def test_staged_never_certified(self):
        row=stage_batch([BAR],symbol="abc.pa",currency="EUR",retrieved_at=NOW,as_of=NOW)[0]
        self.assertFalse(row["point_in_time_verified"])
        self.assertFalse(row["paper_eligible"])
        self.assertIsNone(row["published_at"])
        self.assertEqual(row["quality_status"],"staged_unverified")
    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            stage_batch([BAR,BAR],symbol="ABC.PA",currency="EUR",retrieved_at=NOW,as_of=NOW)
    def test_invalid_ohlcv_rejected(self):
        with self.assertRaisesRegex(ValueError,"OHLCV"):
            stage_batch([{**BAR,"high":9}],symbol="ABC.PA",currency="EUR",retrieved_at=NOW,as_of=NOW)
    def test_future_rejected(self):
        with self.assertRaisesRegex(ValueError,"future"):
            stage_batch([{**BAR,"session_date":"2026-11-22"}],symbol="ABC.PA",currency="EUR",retrieved_at=NOW,as_of=NOW)
    def test_nan_rejected(self):
        with self.assertRaisesRegex(ValueError,"nonfinite"):
            stage_batch([{**BAR,"close":"nan"}],symbol="ABC.PA",currency="EUR",retrieved_at=NOW,as_of=NOW)
    def test_fractional_volume_rejected(self):
        with self.assertRaisesRegex(ValueError,"OHLCV"):
            stage_batch([{**BAR,"volume":1.5}],symbol="ABC.PA",currency="EUR",retrieved_at=NOW,as_of=NOW)
