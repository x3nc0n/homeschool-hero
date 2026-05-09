from fastapi.testclient import TestClient

def test_health_endpoint(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_protects_api_routes(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/students")
    assert response.status_code == 401
