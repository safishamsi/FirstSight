from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_bootstrap_flags() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "facial_droop_api_configured" in response.json()
