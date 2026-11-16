"""Safe MKD-only PostgreSQL logical backup and verification.

Never uses Weinstein'S database. Restore is intentionally not automatic.
"""
import argparse
import hashlib
import os
import subprocess
from pathlib import Path
from sqlalchemy.engine import make_url, URL

def backup(*, destination: Path, database_url: str, runner=subprocess.run):
    if destination.exists():
        raise FileExistsError(destination)
    checksum_path = destination.with_suffix(".dump.sha256")
    if checksum_path.exists():
        raise FileExistsError(checksum_path)
    if destination.suffix != ".dump":
        raise ValueError("backup must use .dump extension")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("PostgreSQL URL required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Password is passed via environment, never in process arguments.
    conninfo = URL.create("postgresql", username=url.username, host=url.host, port=url.port, database=url.database, query=url.query).render_as_string(hide_password=False)
    environment = os.environ.copy()
    if url.password is not None:
        environment["PGPASSWORD"] = url.password
    tmp = destination.with_suffix(".dump.partial")
    if tmp.exists():
        raise FileExistsError(tmp)
    try:
        runner(["pg_dump", "--format=custom", "--no-owner", "--no-acl",
                "--file", str(tmp), conninfo], check=True, env=environment)
        runner(["pg_restore", "--list", str(tmp)], check=True,
               stdout=subprocess.DEVNULL)
        digestor = hashlib.sha256()
        with tmp.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digestor.update(chunk)
        digest = digestor.hexdigest()
        if not digest or tmp.stat().st_size == 0:
            raise ValueError("empty dump")
        tmp.rename(destination)
        checksum_path.write_text(
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
