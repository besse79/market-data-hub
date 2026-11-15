from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_liveness():
    assert client.get("/health/live").json() == {"status": "ok"}

def test_future_cutoff_rejected_without_db():
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    response = client.get("/v1/fx", params={"base":"EUR","quote":"USD","date":"2026-01-02","as_of":future})
    assert response.status_code == 422

def test_unsupported_fx_pair_rejected_without_db():
    response = client.get("/v1/fx", params={"base":"GBP","quote":"USD","date":"2025-01-02","as_of":"2026-01-02T00:00:00Z"})
    assert response.status_code == 422
