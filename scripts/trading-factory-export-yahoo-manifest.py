#!/usr/bin/env python3
"""Read-only MKD instrument manifest export. Never infer unknown currencies."""
import argparse
import csv
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path

import psycopg

DSN = "host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit"
SYMBOL = re.compile(r"^[A-Za-z0-9.^=_-]{1,80}$")
CURRENCIES = {"EUR","USD","GBX","GBP","CHF","SEK","NOK","DKK","PLN","CAD","JPY","AUD"}


def extract(connection):
    with connection.cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        if cur.fetchone() != ("market_data_hub","benoit"):
            raise RuntimeError("Unexpected database or user")
        cur.execute("""SELECT provider, count(*) FROM public.instrument_identifiers
                       GROUP BY provider ORDER BY count(*) DESC""")
        providers = dict(cur.fetchall())
        # Only explicitly mapped Yahoo symbols. Do not guess Yahoo syntax
        # from generic tickers or fabricate EUR/USD currencies.
        cur.execute("""SELECT symbol, currency, instrument_id::text
                       FROM public.instrument_identifiers
                       WHERE lower(provider) = 'yahoo'
                         AND valid_to IS NULL
                       ORDER BY symbol, instrument_id""")
        rows = cur.fetchall()
    good = {}
    rejected = Counter()
    for symbol,currency,instrument_id in rows:
        symbol = (symbol or "").strip()
        currency = (currency or "").strip().upper()
        if not SYMBOL.fullmatch(symbol):
            rejected["invalid_symbol"] += 1
        elif currency not in CURRENCIES:
            rejected["unsupported_or_missing_currency"] += 1
        elif symbol.upper() in good:
            rejected["duplicate_symbol"] += 1
            good.pop(symbol.upper(), None)
        else:
            good[symbol.upper()] = (symbol,currency,instrument_id)
    return sorted(good.values()), {"providers":providers, "rejected":dict(rejected),
                                  "yahoo_active_identifier_rows":len(rows),
                                  "manifest_count":len(good)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    dest=args.output_dir
    if dest.is_symlink(): raise RuntimeError("symlink output directory prohibited")
    dest.mkdir(parents=True,exist_ok=True)
    with psycopg.connect(DSN, options="-c default_transaction_read_only=on") as connection:
        records,report=extract(connection)
    if not records: raise RuntimeError("No verified Yahoo identifier mapping; refusing speculative manifest")
    with tempfile.NamedTemporaryFile(mode="w",newline="",encoding="utf-8",
           dir=dest,prefix=".manifest-",suffix=".csv",delete=False) as f:
        tmp=Path(f.name)
        writer=csv.writer(f);writer.writerow(("symbol","currency"))
        writer.writerows((s,c) for s,c,_ in records)
        f.flush();os.fsync(f.fileno())
    output=dest/"yahoo-manifest.csv"
    try:
        os.link(tmp,output)
    finally:
        tmp.unlink(missing_ok=True)
    print(json.dumps({**report,"manifest":str(output)},indent=2))
    if report["rejected"]:
        print("WARN: rejected mappings require review")
if __name__=="__main__":main()
