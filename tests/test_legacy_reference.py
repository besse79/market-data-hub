import csv
import pytest
from app.legacy_reference import generate

def test_reference_quarantines_unsuffixed_us(tmp_path):
    source = tmp_path / "bars.csv"
    with source.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol","name","currency","day","open","high","low","close","volume"])
        w.writerow(["AAPL","Apple","USD","2026-01-02",1,2,1,2,100])
        w.writerow(["AIR.PA","Airbus","EUR","2026-01-02",1,2,1,2,100])
    report = generate(source, tmp_path / "out")
    assert report["counts"]["bars"] == 2
    assert report["counts"]["candidate_symbols"] == 1
    assert report["counts"]["unresolved_symbols"] == 1
    assert "AAPL" in (tmp_path / "out" / "weinstein-mic-unresolved.csv").read_text()
    assert "XPAR" in (tmp_path / "out" / "weinstein-mic-candidates.csv").read_text()

def test_reference_rejects_duplicate_or_unsorted(tmp_path):
    source = tmp_path / "bars.csv"
    source.write_text("symbol,name,currency,day,open,high,low,close,volume\\nAAPL,Apple,USD,2026-01-02,1,2,1,2,100\\nAAPL,Apple,USD,2026-01-02,1,2,1,2,100\\n".replace("\\n","\n"))
    with pytest.raises(ValueError, match="strictly ordered"):
        generate(source, tmp_path / "out")
