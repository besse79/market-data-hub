from datetime import date
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock
import pytest
from app.collector import collect_one

def test_fetch_normalize_import(monkeypatch):
    from app import collector
    saved = []
    monkeypatch.setattr(collector, "import_bar",
                        lambda db, raw, dry_run=False: saved.append(raw) or "created")
    sample = {"Open": 10, "High": 12, "Low": 9, "Close": 11, "Volume": 100}
    fetch = Mock(return_value=[(date(2026, 11, 13), sample)])
    result = collect_one(object(), instrument_id=uuid4(), symbol="TEST",
                         currency="EUR", start=date(2026, 11, 13),
                         end=date(2026, 11, 14), fetch=fetch)
    assert result["created"] == 1
    assert saved[0]["provider"] == "yahoo"
    assert saved[0]["first_available_at"].startswith("2026-")
    fetch.assert_called_once()

def test_reject_out_of_range_provider_row():
    sample = {"Open": 10, "High": 12, "Low": 9, "Close": 11, "Volume": 100}
    with pytest.raises(ValueError, match="out-of-range"):
        collect_one(object(), instrument_id=uuid4(), symbol="TEST", currency="EUR",
                    start=date(2026, 11, 13), end=date(2026, 11, 14),
                    fetch=lambda *args: [(date(2026, 11, 12), sample)])
