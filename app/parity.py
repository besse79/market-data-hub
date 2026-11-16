"""Offline read-only comparison of W reference manifest and MKD coverage JSON.

No database connection is made; equality of identifiers is not OHLCV parity.
"""
import argparse
import csv
import json
from pathlib import Path

def compare(manifest: Path, coverage_json: Path):
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"symbol", "mic", "currency"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("W manifest requires symbol,mic,currency")
        expected = {}
        for line, row in enumerate(reader, 2):
            key = tuple((row.get(k) or "").strip().upper() for k in ("symbol", "mic"))
            currency = (row.get("currency") or "").strip().upper()
            if not all(key) or len(currency) != 3:
                raise ValueError(f"invalid W identifier line {line}")
            if key in expected:
                raise ValueError(f"duplicate W identifier {key}")
            expected[key] = currency
    data = json.loads(coverage_json.read_text(encoding="utf-8"))
    observed = {}
    for item in data["instruments"]:
        key = (item["symbol"].strip().upper(), item["mic"].strip().upper())
        if key in observed:
            raise ValueError(f"duplicate MKD identifier {key}")
        observed[key] = item
    missing = sorted(set(expected) - set(observed))
    extra = sorted(set(observed) - set(expected))
    mismatch = sorted(key for key in set(expected) & set(observed)
                      if expected[key] != observed[key]["currency"].upper())
    insufficient = sorted(key for key in set(expected) & set(observed)
                          if observed[key]["status"] != "sufficient")
    return {
        "w_count": len(expected), "mkd_count": len(observed),
        "missing_in_mkd": [list(k) for k in missing],
        "extra_in_mkd": [list(k) for k in extra],
        "currency_mismatches": [list(k) for k in mismatch],
        "insufficient_history": [list(k) for k in insufficient],
        "identifier_parity": not (missing or extra or mismatch),
        "coverage_complete": not insufficient and not missing,
        "ohlcv_parity_verified": False,
    }

def main():
    parser = argparse.ArgumentParser(description="Offline W/MKD identifier parity (not OHLCV parity)")
    parser.add_argument("w_manifest", type=Path)
    parser.add_argument("mkd_coverage", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare(args.w_manifest, args.mkd_coverage)
    content = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    print(content, end="")
    if not result["identifier_parity"] or not result["coverage_complete"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
