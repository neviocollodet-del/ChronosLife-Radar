import pytest
pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)


def test_health():
    assert c.get("/health").json()["status"] == "ok"


def test_sector_ids_match_android_app():
    assert [s["id"] for s in c.get("/v1/sectors").json()] == ["ai-tech", "operations", "sport"]


def test_trends_contract(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.DB_PATH", str(tmp_path / "t.db"))
    j = c.get("/v1/trends", params={"sector_id": "ai-tech", "window_days": 90}).json()
    assert set(j) >= {"items", "data_status"} and j["items"] == []
    assert c.get("/v1/trends", params={"sector_id": "x"}).status_code == 404
