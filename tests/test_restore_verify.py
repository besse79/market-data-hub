import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.restore_verify import verify_checksum, restore_to_empty

def fixture_dump(tmp_path):
    p = tmp_path / "mkd.dump"
    p.write_bytes(b"archive")
    p.with_suffix(".dump.sha256").write_text(
        hashlib.sha256(b"archive").hexdigest() + "  mkd.dump\n")
    return p

def test_checksum_valid(tmp_path):
    assert verify_checksum(fixture_dump(tmp_path)) == hashlib.sha256(b"archive").hexdigest()

def test_checksum_rejects_tamper(tmp_path):
    p = fixture_dump(tmp_path)
    p.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        verify_checksum(p)

def test_restore_rejects_source_database(tmp_path):
    p = fixture_dump(tmp_path)
    with pytest.raises(ValueError, match="source and destination"):
        restore_to_empty(dump=p, source_url="postgresql://localhost/mkd_restore_test",
                         target_url="postgresql://localhost/mkd_restore_test", runner=Mock())

def test_restore_rejects_non_disposable_target(tmp_path):
    with pytest.raises(ValueError, match="end with"):
        restore_to_empty(dump=fixture_dump(tmp_path),
                         source_url="postgresql://localhost/mkd",
                         target_url="postgresql://localhost/production", runner=Mock())

def test_restore_refuses_nonempty_target(tmp_path):
    runner = Mock(return_value=SimpleNamespace(stdout="2\n"))
    with pytest.raises(ValueError, match="not empty"):
        restore_to_empty(dump=fixture_dump(tmp_path),
                         source_url="postgresql://localhost/mkd",
                         target_url="postgresql://localhost/mkd_restore_test", runner=runner)
    assert runner.call_count == 1

def test_restore_to_empty(tmp_path):
    runner = Mock(return_value=SimpleNamespace(stdout="0\n"))
    result = restore_to_empty(dump=fixture_dump(tmp_path),
                             source_url="postgresql://localhost/mkd",
                             target_url="postgresql://localhost/mkd_restore_test", runner=runner)
    assert result["restored_to"] == "mkd_restore_test"
    assert runner.call_count == 2
    assert runner.call_args.args[0][0] == "pg_restore"

def test_restore_password_not_in_arguments(tmp_path):
    calls = []
    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="0\n")
    restore_to_empty(dump=fixture_dump(tmp_path),
                     source_url="postgresql://localhost/mkd",
                     target_url="postgresql+psycopg://mkd:secret-pass@localhost/mkd_restore_test",
                     runner=runner)
    assert len(calls) == 2
    for args, kwargs in calls:
        assert "secret-pass" not in " ".join(args)
        assert kwargs["env"]["PGPASSWORD"] == "secret-pass"

@pytest.mark.parametrize("digest", ["abc", "g" * 64, "A" * 64, "0" * 63])
def test_restore_rejects_malformed_checksum_before_database_access(tmp_path, digest):
    p = fixture_dump(tmp_path)
    p.with_suffix(".dump.sha256").write_text(f"{digest}  mkd.dump\n")
    runner = Mock()
    with pytest.raises(ValueError, match="invalid checksum manifest"):
        restore_to_empty(dump=p, source_url="postgresql://localhost/mkd",
                         target_url="postgresql://localhost/mkd_restore_test", runner=runner)
    runner.assert_not_called()
