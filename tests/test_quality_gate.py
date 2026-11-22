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

 def test_unsorted_rejected(self):
  a=dict(day='2026-11-19',open=10,high=11,low=9,close=10,volume=100)
  b=dict(a,day='2026-11-18')
  self.assertIn('UNSORTED_HISTORY',assess_bars([a,b],'2026-11-20','EUR','point_in_time_verified')['reasons'])
 def test_bad_cutoff_fails_closed(self):
  a=dict(day='2026-11-19',open=10,high=11,low=9,close=10,volume=100)
  self.assertIn('INVALID_AS_OF',assess_bars([a],'not-a-date','EUR','point_in_time_verified')['reasons'])
 def test_malformed_history_fails_closed(self):
  self.assertIn('INVALID_HISTORY',assess_bars(None,'2026-11-20','EUR','point_in_time_verified')['reasons'])
 def test_nan_and_inverted_prices_rejected(self):
  a=dict(day='2026-11-19',open=10,high=9,low=11,close=10,volume=100)
  self.assertIn('INVALID_OHLCV',assess_bars([a],'2026-11-20','EUR','point_in_time_verified')['reasons'])
  a['volume']=float('nan')
  self.assertIn('INVALID_OHLCV',assess_bars([a],'2026-11-20','EUR','point_in_time_verified')['reasons'])
