#!/usr/bin/env python3
"""Yahoo daily capture into an atomic JSON research staging artifact.

Does NOT write to PostgreSQL, certify PIT, or authorize PAPER orders.
Actual retrieval time is not the provider's historical publication time.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.daily_stage import stage_batch


def capture(symbol, currency, start, end, output, *, fetcher=None):
    if fetcher is None:
        import yfinance as yf
        fetcher = yf.download
    began = datetime.now(timezone.utc)
    frame = fetcher(symbol, start=start, end=end, auto_adjust=False,
                    actions=False, progress=False, threads=False)
    received = datetime.now(timezone.utc)
    if frame is None or frame.empty:
        raise ValueError(f"empty Yahoo response for {symbol}")
    if getattr(frame.columns, "nlevels", 1) > 1:
        # yfinance versions differ in whether ticker is the first or last level.
        if symbol in frame.columns.get_level_values(-1):
            frame = frame.xs(symbol, axis=1, level=-1)
        elif symbol in frame.columns.get_level_values(0):
            frame = frame.xs(symbol, axis=1, level=0)
        else:
            raise ValueError("ambiguous multi-ticker Yahoo response")
    required = ("Open", "High", "Low", "Close", "Volume")
    if any(key not in frame.columns for key in required):
        raise ValueError("missing OHLCV columns")
    rows = []
    for index, row in frame.iterrows():
        rows.append({
            "session_date": index.date().isoformat(),
            **{name.lower(): row[name] for name in required},
        })
    validated = stage_batch(rows, symbol=symbol, currency=currency,
                            retrieved_at=received)
    document = {
        "schema_version": 1,
        "provider": "yahoo",
        "source_symbol": symbol,
        "currency": currency,
        "request_started_at": began.isoformat(),
        "response_received_at": received.isoformat(),
        "request_start": start,
        "request_end_exclusive": end,
        "point_in_time_verified": False,
        "backtest_eligible": False,
        "paper_eligible": False,
        "execution_authorized": False,
        "observations": validated,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                prefix=".mkd-stage-", suffix=".json", dir=output.parent,
                delete=False) as tmp:
            temp_name = tmp.name
            json.dump(document, tmp, indent=2, ensure_ascii=False)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.chmod(temp_name, 0o600)
        # Exclusive creation, never replace an existing report.
        os.link(temp_name, output)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return len(validated)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--currency", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    from datetime import date
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if start >= end or end > datetime.now(timezone.utc).date():
        parser.error("invalid or future date window (end exclusive)")
    count = capture(args.symbol, args.currency, args.start, args.end, args.output)
    print(f"STAGED={count} OUTPUT={args.output} PIT=false PAPER=false")


if __name__ == "__main__":
    main()
