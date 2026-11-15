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
