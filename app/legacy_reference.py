"""Generate a conservative instrument manifest from the sorted Weinstein CSV.

Never guess the MIC of unsuffixed US tickers. Candidate suffix mapping is
reported for review, not automatically promoted to verified metadata.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

SUFFIX_MIC = {
    ".L": "XLON", ".DE": "XETR", ".PA": "XPAR", ".SW": "XSWX",
    ".ST": "XSTO", ".MI": "XMIL", ".AS": "XAMS", ".MC": "XMAD",
    ".CO": "XCSE", ".OL": "XOSL", ".HE": "XHEL", ".WA": "XWAR",
    ".BR": "XBRU", ".VI": "XWBO", ".IR": "XDUB", ".LS": "XLIS",
}
REQUIRED = {"symbol", "name", "currency", "day", "open", "high", "low", "close", "volume"}

def generate(source: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    counts = Counter()
    last = None
    with source.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError("missing columns")
        for row in reader:
            symbol = row["symbol"].strip().upper()
            name = row["name"].strip()
            currency = row["currency"].strip().upper()
            day = row["day"].strip()
            if not symbol or not name or len(currency) != 3:
                raise ValueError("invalid instrument metadata")
            key = (symbol, day)
            if last is not None and key <= last:
                raise ValueError(f"source must be strictly ordered and unique: {key}")
            last = key
            metadata = (name, currency)
            if symbol in records and records[symbol][:2] != metadata:
                raise ValueError(f"inconsistent metadata: {symbol}")
            if symbol not in records:
                suffix = next((s for s in sorted(SUFFIX_MIC, key=len, reverse=True) if symbol.endswith(s)), None)
                records[symbol] = (name, currency, SUFFIX_MIC.get(suffix), 0)
            n, c, mic, bar_count = records[symbol]
            records[symbol] = (n, c, mic, bar_count + 1)
            counts["bars"] += 1
    candidates = output / "weinstein-mic-candidates.csv"
    unresolved = output / "weinstein-mic-unresolved.csv"
    with candidates.open("w", newline="", encoding="utf-8") as yes, unresolved.open("w", newline="", encoding="utf-8") as no:
        wyes, wno = csv.writer(yes), csv.writer(no)
        wyes.writerow(["symbol", "name", "currency", "candidate_mic", "bars", "review_status"])
        wno.writerow(["symbol", "name", "currency", "bars", "reason"])
        for symbol, (name, currency, mic, n) in sorted(records.items()):
            if mic:
                wyes.writerow([symbol, name, currency, mic, n, "needs_verification"])
                counts["candidate_symbols"] += 1
                counts["candidate_bars"] += n
            else:
                wno.writerow([symbol, name, currency, n, "exchange_mic_unknown"])
                counts["unresolved_symbols"] += 1
                counts["unresolved_bars"] += n
    counts["symbols"] = len(records)
    report = {"status": "review_required", "counts": dict(counts),
              "candidate_file": str(candidates), "unresolved_file": str(unresolved)}
    (output / "weinstein-reference-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=Path)
    p.add_argument("--output", type=Path, default=Path("evidence"))
    args = p.parse_args()
    print(json.dumps(generate(args.csv, args.output), indent=2))

if __name__ == "__main__":
    main()
