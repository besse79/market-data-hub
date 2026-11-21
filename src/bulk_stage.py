"""Bounded, resumable, fail-closed Yahoo staging; never touches PostgreSQL."""
import csv
import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from src.yahoo_capture import capture

SAFE_SYMBOL = re.compile(r"^[A-Za-z0-9.^=_-]{1,80}$")
CURRENCIES = {"EUR","USD","GBX","GBP","CHF","SEK","NOK","DKK","PLN","CAD","JPY","AUD"}


def run(manifest, output_dir, start, end, *, max_symbols=25, delay=2.0,
        capture_fn=capture, sleep_fn=time.sleep):
    if not 1 <= max_symbols <= 1104 or delay < 1:
        raise ValueError("unsafe batch settings")
    start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    if start_date >= end_date or end_date > datetime.now(timezone.utc).date():
        raise ValueError("invalid date window")
    output_dir = Path(output_dir)
    if output_dir.is_symlink():
        raise ValueError("symlink output directory prohibited")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = Path(manifest)
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not {"symbol","currency"} <= set(reader.fieldnames):
            raise ValueError("manifest requires symbol,currency")
        items = list(reader)
    if not items or len(items) > 1104:
        raise ValueError("invalid manifest size")
    seen = set()
    for item in items:
        symbol, currency = item["symbol"].strip(), item["currency"].strip().upper()
        if not SAFE_SYMBOL.fullmatch(symbol) or currency not in CURRENCIES:
            raise ValueError(f"invalid manifest entry: {symbol!r}/{currency!r}")
        if symbol.upper() in seen:
            raise ValueError("duplicate symbol in manifest")
        seen.add(symbol.upper())
    summary = {"requested": min(len(items),max_symbols), "success":0,
               "skipped":0, "failed":0, "failures":[], "paper_eligible":False,
               "point_in_time_verified":False}
    for idx,item in enumerate(items[:max_symbols]):
        symbol,currency = item["symbol"].strip(),item["currency"].strip().upper()
        target = output_dir / f"{symbol.upper()}-{start}-{end}.json"
        if target.exists():
            try:
                data=json.loads(target.read_text(encoding="utf-8"))
                if (data.get("source_symbol","").upper()==symbol.upper()
                    and data.get("currency")==currency
                    and data.get("request_start")==start
                    and data.get("request_end_exclusive")==end
                    and data.get("paper_eligible") is False
                    and data.get("point_in_time_verified") is False
                    and data.get("observations")
                    and all(r.get("quality_status")=="staged_unverified" for r in data["observations"])):
                    summary["skipped"]+=1
                    continue
            except (OSError,ValueError,TypeError):
                pass
            summary["failed"]+=1
            summary["failures"].append({"symbol":symbol,"reason":"existing output invalid or incompatible"})
            continue
        if idx:
            sleep_fn(delay)
        try:
            capture_fn(symbol,currency,start,end,target)
            summary["success"]+=1
        except Exception as exc:
            summary["failed"]+=1
            summary["failures"].append({"symbol":symbol,"reason":str(exc)[:200]})
    return summary
