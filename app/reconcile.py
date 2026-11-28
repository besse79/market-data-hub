"""Read-only reconciliation of W export manifest against MKD instrument universe.

No access to W database. CSV is explicit, read-only and never modified.
"""
import argparse
import csv
import json
from pathlib import Path
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Identifier, Instrument
from app.universe import parse_manifest

def reconcile(db, manifest):
    expected = parse_manifest(manifest)
    existing = db.execute(select(Identifier, Instrument).join(
        Instrument, Instrument.id == Identifier.instrument_id
    ).where(Identifier.provider == "yahoo", Identifier.valid_to.is_(None))).all()
    by_key = {}
    for ident, inst in existing:
        key = (ident.symbol.upper(), ident.mic.upper())
        by_key.setdefault(key, []).append((ident, inst))
    report = {"expected": len(expected), "matched": 0, "missing": [],
              "conflicts": [], "extra": [], "ready": False}
    keys = set()
    for row in expected:
        key = (row["symbol"], row["mic"])
        keys.add(key)
        candidates = by_key.get(key, [])
        if not candidates:
            report["missing"].append({"symbol": key[0], "mic": key[1]})
        elif len(candidates) != 1:
            report["conflicts"].append({"symbol": key[0], "mic": key[1],
                                        "reason": "ambiguous identifier"})
        else:
            ident, inst = candidates[0]
            mismatches = [field for field, got, want in (
                ("currency", ident.currency, row["currency"]),
                ("name", inst.name, row["name"]),
                ("asset_type", inst.asset_type, row["asset_type"])
            ) if got != want]
            if mismatches:
                report["conflicts"].append({"symbol": key[0], "mic": key[1],
                                            "reason": "metadata mismatch",
                                            "fields": mismatches})
            else:
                report["matched"] += 1
    report["extra"] = [{"symbol": sym, "mic": mic}
                       for sym, mic in sorted(by_key) if (sym, mic) not in keys]
    report["ready"] = not report["missing"] and not report["conflicts"]
    return report

def main():
    parser = argparse.ArgumentParser(description="Read-only W/MKD instrument reconciliation")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    with SessionLocal() as db:
        report = reconcile(db, args.manifest)
    result = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)
    if not report["ready"]:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
