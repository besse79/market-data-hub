"""Conservative readiness decisions based on aggregate MKD audit counters.

Aggregate counts never establish point-in-time provenance, source freshness,
corporate-action correctness or end-to-end backtest reproducibility.
"""
def evaluate_readiness(*, certified_bars, invalid_certified,
                       invalid_ohlcv, legacy_provenance_violations,
                       mic_unverified, fx_rows):
    counts = (certified_bars, invalid_certified, invalid_ohlcv,
              legacy_provenance_violations, mic_unverified, fx_rows)
    if any(type(x) is not int or x < 0 for x in counts):
        raise ValueError("Readiness counters must be nonnegative integers")
    reasons = []
    if certified_bars == 0:
        reasons.append("NO_CERTIFIED_BARS")
    if invalid_certified:
        reasons.append("INVALID_CERTIFIED_BARS")
    if invalid_ohlcv:
        reasons.append("INVALID_OHLCV")
    if legacy_provenance_violations:
        reasons.append("LEGACY_PROVENANCE_INCONSISTENT")
    if mic_unverified:
        reasons.append("UNVERIFIED_MIC_MAPPING")
    if fx_rows == 0:
        reasons.append("NO_FX_ROWS")
    # Aggregate checks are necessary but never sufficient to certify PIT.
    reasons.append("PIT_PROVENANCE_FRESHNESS_AND_PARITY_NOT_ATTESTED")
    return {
        "structural_checks_pass": len(reasons) == 1,
        "pit_backtest_ready": False,
        "paper_trading_authorized": False,
        "readiness_blockers": reasons,
    }
