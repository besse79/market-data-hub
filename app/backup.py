"""Safe MKD-only PostgreSQL logical backup and verification.

Never uses Weinstein'S database. Restore is intentionally not automatic.
"""
import argparse
import hashlib
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone

def backup(*, destination: Path, database_url: str, runner=subprocess.run):
    if destination.exists():
        raise FileExistsError(destination)
    if destination.suffix != ".dump":
        raise ValueError("backup must use .dump extension")
    if not database_url.startswith("postgresql"):
        raise ValueError("PostgreSQL URL required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # psycopg SQLAlchemy URL prefix is not understood by libpq.
    libpq_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    tmp = destination.with_suffix(".dump.partial")
    if tmp.exists():
        raise FileExistsError(tmp)
    try:
        runner(["pg_dump", "--format=custom", "--no-owner", "--no-acl",
                "--file", str(tmp), libpq_url], check=True)
        runner(["pg_restore", "--list", str(tmp)], check=True,
               stdout=subprocess.DEVNULL)
        digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if not digest or tmp.stat().st_size == 0:
            raise ValueError("empty dump")
        tmp.rename(destination)
        destination.with_suffix(".dump.sha256").write_text(
            f"{digest}  {destination.name}\n", encoding="utf-8")
        return {"file": str(destination), "sha256": digest, "bytes": destination.stat().st_size}
    finally:
        if tmp.exists():
            tmp.unlink()

def main():
    parser = argparse.ArgumentParser(description="MKD isolated pg_dump backup")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL is required")
    print(backup(destination=args.destination, database_url=url))

if __name__ == "__main__":
    main()
