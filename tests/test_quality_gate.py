import unittest
from src.quality_gate import assess_bars

class QualityTest(unittest.TestCase):
 def test_legacy_never_verified(self):
  bars=[dict(day='2026-11-19',open=10,high=11,low=9,close=10,volume=100)]
  self.assertIn('UNVERIFIED_PROVENANCE',assess_bars(bars,'2026-11-20','EUR','legacy_unverified')['reasons'])
 def test_future_and_duplicate_blocked(self):
  bar=dict(day='2026-11-21',open=10,high=11,low=9,close=10,volume=100)
  reasons=assess_bars([bar,bar],'2026-11-20','EUR','point_in_time_verified')['reasons']
  self.assertIn('FUTURE_BAR',reasons)
  self.assertIn('DUPLICATE_DAY',reasons)
