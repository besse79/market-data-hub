import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from mkd_readiness import evaluate_readiness

class ReadinessTests(unittest.TestCase):
    def test_no_certified_bars_blocks(self):
        result = evaluate_readiness(certified_bars=0, invalid_certified=0,
            invalid_ohlcv=0, legacy_provenance_violations=0,
            mic_unverified=0, fx_rows=0)
        self.assertIn("NO_CERTIFIED_BARS", result["readiness_blockers"])
        self.assertFalse(result["pit_backtest_ready"])

    def test_clean_aggregate_still_does_not_attest_pit(self):
        result = evaluate_readiness(certified_bars=100000, invalid_certified=0,
            invalid_ohlcv=0, legacy_provenance_violations=0,
            mic_unverified=0, fx_rows=200)
        self.assertTrue(result["structural_checks_pass"])
        self.assertFalse(result["pit_backtest_ready"])
        self.assertFalse(result["paper_trading_authorized"])
        self.assertIn("PIT_PROVENANCE_FRESHNESS_AND_PARITY_NOT_ATTESTED",
                      result["readiness_blockers"])

    def test_bad_counters_fail_closed(self):
        values = dict(certified_bars=1, invalid_certified=0, invalid_ohlcv=0,
                      legacy_provenance_violations=0, mic_unverified=0, fx_rows=1)
        for bad in (-1, True, 1.5, None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    evaluate_readiness(**{**values, "certified_bars": bad})

    def test_structural_anomalies_are_explicit(self):
        result = evaluate_readiness(certified_bars=100, invalid_certified=2,
            invalid_ohlcv=1, legacy_provenance_violations=3,
            mic_unverified=4, fx_rows=0)
        self.assertFalse(result["structural_checks_pass"])
        self.assertEqual(set(result["readiness_blockers"]), {
            "INVALID_CERTIFIED_BARS", "INVALID_OHLCV",
            "LEGACY_PROVENANCE_INCONSISTENT", "UNVERIFIED_MIC_MAPPING",
            "NO_FX_ROWS", "PIT_PROVENANCE_FRESHNESS_AND_PARITY_NOT_ATTESTED"})
if __name__ == "__main__":
    unittest.main()
