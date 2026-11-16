from types import SimpleNamespace
from unittest.mock import Mock
from app.reconcile import reconcile

def write_manifest(tmp_path):
    p = tmp_path / "w.csv"
    p.write_text("symbol,mic,currency,name,asset_type\nAAPL,XNAS,USD,Apple,equity\nMSFT,XNAS,USD,Microsoft,equity\n", encoding="utf-8")
    return p

def test_reconcile_missing(tmp_path):
    p = write_manifest(tmp_path)
    ident = SimpleNamespace(symbol="AAPL", mic="XNAS", currency="USD")
    inst = SimpleNamespace(name="Apple", asset_type="equity")
    db = Mock()
    db.execute.return_value.all.return_value = [(ident, inst)]
    report = reconcile(db, p)
    assert report["matched"] == 1
    assert report["missing"] == [{"symbol": "MSFT", "mic": "XNAS"}]
    assert report["ready"] is False

def test_reconcile_complete(tmp_path):
    p = write_manifest(tmp_path)
    rows = [(SimpleNamespace(symbol=s, mic="XNAS", currency="USD"),
             SimpleNamespace(name=n, asset_type="equity"))
            for s, n in [("AAPL", "Apple"), ("MSFT", "Microsoft")]]
    db = Mock()
    db.execute.return_value.all.return_value = rows
    report = reconcile(db, p)
    assert report["matched"] == 2
    assert report["ready"] is True

def test_reconcile_metadata_conflict(tmp_path):
    p = write_manifest(tmp_path)
    ident = SimpleNamespace(symbol="AAPL", mic="XNAS", currency="EUR")
    inst = SimpleNamespace(name="Apple", asset_type="equity")
    db = Mock()
    db.execute.return_value.all.return_value = [(ident, inst)]
    report = reconcile(db, p)
    assert report["conflicts"][0]["fields"] == ["currency"]
