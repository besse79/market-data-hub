import unittest
from datetime import datetime,timezone
from decimal import Decimal
from src.fx_stage import fx_requirement, stage_fx, convert_to_eur

class FXTests(unittest.TestCase):
    def test_gbx_pence(self):
        self.assertEqual(convert_to_eur(100,"GBX",Decimal("0.8")),Decimal("1.25"))
    def test_usd_conversion(self):
        self.assertEqual(convert_to_eur(110,"USD",Decimal("1.1")),Decimal("100"))
    def test_eur_identity(self):
        self.assertEqual(convert_to_eur(100,"EUR",None),Decimal("100"))
    def test_missing_fx_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"FX missing"):
            convert_to_eur(10,"CHF",None)
    def test_bad_fx_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"invalid FX"):
            convert_to_eur(10,"USD",0)
    def test_staged_fx_never_pit(self):
        r=stage_fx("EUR","USD","2026-11-20",1.1,datetime(2026,11,21,tzinfo=timezone.utc))
        self.assertFalse(r["point_in_time_verified"])
        self.assertFalse(r["paper_eligible"])
        self.assertIsNone(r["published_at"])
    def test_invalid_currency(self):
        with self.assertRaises(ValueError):
            fx_requirement("ZZZ")
