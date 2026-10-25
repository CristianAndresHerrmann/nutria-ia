from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_responde_ok_con_timestamp_utc():
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "nutria-ia"
    assert datetime.fromisoformat(body["timestamp"]).utcoffset() is not None
