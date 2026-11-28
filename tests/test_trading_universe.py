import unittest
from app.universe import trading_universe

class TradingUniverseTests(unittest.TestCase):
    def test_scope(self):
        rows=[dict(currency=c,asset_type=t) for c,t in [("EUR","equity"),("USD","stock"),("GBP","equity"),("EUR","bond")]]
        self.assertEqual(trading_universe(rows),rows[:2])
        with self.assertRaises(ValueError):
            trading_universe(rows[2:])
