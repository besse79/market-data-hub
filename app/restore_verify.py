"""Verify a MKD backup by restoring into an explicitly named disposable database.

This script never creates/drops databases and refuses the source database.
The destination must already exist and be empty; no --clean is used.
"""
import argparse
import hashlib
import os
import subprocess
from pathlib import Path
from sqlalchemy.engine import make_url, URL

def verify_checksum(dump: Path):
    if not dump.is_file() or dump.suffix != ".dump":
        raise ValueError("existing .dump file required")
    checksum = dump.with_suffix(".dump.sha256")
    expected_parts = checksum.read_text(encoding="utf-8").strip().split()
    if (len(expected_parts) != 2 or expected_parts[1] != dump.name
            or len(expected_parts[0]) != 64
            or any(ch not in "0123456789abcdef" for ch in expected_parts[0])):
        raise ValueError("invalid checksum manifest")
    digest = hashlib.sha256()
    with dump.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_parts[0]:
        raise ValueError("backup checksum mismatch")
    return digest.hexdigest()

def restore_to_empty(*, dump: Path, source_url: str, target_url: str,
                     runner=subprocess.run):
    verify_checksum(dump)
    source = make_url(source_url)
    target = make_url(target_url)
    if source.get_backend_name() != "postgresql" or target.get_backend_name() != "postgresql":
        raise ValueError("PostgreSQL connections required")
    if not target.database or not target.database.endswith("_restore_test"):
        raise ValueError("destination database must end with _restore_test")
    if (source.host, source.port or 5432, source.database) == (
            target.host, target.port or 5432, target.database):
        raise ValueError("source and destination must differ")
    env = os.environ.copy()
    if target.password is not None:
        env["PGPASSWORD"] = target.password
    conninfo = URL.create("postgresql", username=target.username, host=target.host, port=target.port, database=target.database, query=target.query).render_as_string(hide_password=False)
    # Refuse nonempty target before invoking pg_restore. No destructive cleanup.
    probe = runner(["psql", "--no-psqlrc", "--tuples-only", "--no-align",
                    "--dbname", conninfo, "--command",
                    "SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','S','f')"],
                   check=True, capture_output=True, text=True, env=env)
    if probe.stdout.strip() != "0":
        raise ValueError("destination is not empty")
    runner(["pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
            "--dbname", conninfo, str(dump)], check=True, env=env)
    return {"restored_to": target.database, "sha256": verify_checksum(dump)}

def main():
    parser = argparse.ArgumentParser(description="Verify restore into an existing empty disposable database")
    parser.add_argument("dump", type=Path)
    parser.add_argument("--target-url-env", default="MKD_RESTORE_TEST_URL")
    args = parser.parse_args()
    source = os.environ.get("DATABASE_URL")
    target = os.environ.get(args.target_url_env)
    if not source or not target:
        parser.error("DATABASE_URL and target URL environment variable are required")
    print(restore_to_empty(dump=args.dump, source_url=source, target_url=target))

if __name__ == "__main__":
    main()
