from fastapi.testclient import TestClient


def test_health_endpoint(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"healthy", "degraded", "unhealthy"}
    assert "ready" in payload
    assert "checked_at" in payload
    assert "maintenance" in payload


def test_capabilities_endpoint_returns_current_flags(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "capabilities" in payload
    assert {"ai_grading", "email", "backup", "ocr"} <= set(payload["capabilities"])
    assert payload["auth"]["local_enabled"] is True


def test_auth_protects_api_routes(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/students")
    assert response.status_code == 401
