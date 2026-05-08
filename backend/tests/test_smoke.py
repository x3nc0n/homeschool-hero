from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_protects_api_routes() -> None:
    response = client.get("/api/students")
    assert response.status_code == 401
