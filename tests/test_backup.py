from pathlib import Path
from unittest.mock import Mock
import pytest
from app.backup import backup

def test_refuse_overwrite(tmp_path):
    path = tmp_path / "mkd.dump"
    path.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        backup(destination=path, database_url="postgresql://localhost/mkd")

def test_backup_checks_dump_and_checksum(tmp_path):
    def fake_run(args, **kwargs):
        if args[0] == "pg_dump":
            Path(args[args.index("--file") + 1]).write_bytes(b"test dump")
        return Mock(returncode=0)
    path = tmp_path / "mkd.dump"
    result = backup(destination=path, database_url="postgresql+psycopg://localhost/mkd", runner=fake_run)
    assert result["bytes"] == 9
    assert path.with_suffix(".dump.sha256").exists()

def test_backup_failure_removes_partial(tmp_path):
    def failing(*args, **kwargs):
        raise RuntimeError("pg_dump failed")
    path = tmp_path / "mkd.dump"
    with pytest.raises(RuntimeError):
        backup(destination=path, database_url="postgresql://localhost/mkd", runner=failing)
    assert not path.exists()
    assert not path.with_suffix(".dump.partial").exists()

def test_backup_does_not_expose_password_in_process_arguments(tmp_path):
    calls = []
    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == "pg_dump":
            Path(args[args.index("--file") + 1]).write_bytes(b"test dump")
        return Mock(returncode=0)
    path = tmp_path / "secure.dump"
    backup(destination=path,
           database_url="postgresql+psycopg://mkd:very-secret@localhost:5432/mkd",
           runner=fake_run)
    dump_args, dump_kwargs = calls[0]
    assert "very-secret" not in " ".join(dump_args)
    assert dump_kwargs["env"]["PGPASSWORD"] == "very-secret"
    assert "very-secret" not in str(calls[1][0])


def test_refuse_existing_checksum_without_running_dump(tmp_path):
    path = tmp_path / "mkd.dump"
    sidecar = path.with_suffix(".dump.sha256")
    sidecar.write_text("existing checksum", encoding="utf-8")
    runner = Mock()
    with pytest.raises(FileExistsError):
        backup(destination=path, database_url="postgresql://localhost/mkd", runner=runner)
    runner.assert_not_called()
    assert sidecar.read_text(encoding="utf-8") == "existing checksum"
    assert not path.exists()


def test_backup_rejects_invalid_archive_and_cleans_partial(tmp_path):
    calls = []
    def fake_run(args, **kwargs):
        calls.append(args[0])
        if args[0] == "pg_dump":
            Path(args[args.index("--file") + 1]).write_bytes(b"invalid dump")
        elif args[0] == "pg_restore":
            raise RuntimeError("archive validation failed")
        return Mock(returncode=0)
    path = tmp_path / "mkd.dump"
    with pytest.raises(RuntimeError, match="archive validation failed"):
        backup(destination=path, database_url="postgresql://localhost/mkd", runner=fake_run)
    assert calls == ["pg_dump", "pg_restore"]
    assert not path.exists()
    assert not path.with_suffix(".dump.partial").exists()
    assert not path.with_suffix(".dump.sha256").exists()
