from fastapi.testclient import TestClient


def test_health_endpoint(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "ready" in payload
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
    assert payload["features"]["online_curriculum_enabled"] is True


def test_capabilities_endpoint_reports_online_curriculum_gate(app, monkeypatch) -> None:
    monkeypatch.setattr('backend.config.settings.online_curriculum_enabled', False, raising=False)
    with TestClient(app) as client:
        response = client.get("/api/capabilities")
    assert response.status_code == 200
    assert response.json()["features"]["online_curriculum_enabled"] is False


def test_auth_protects_api_routes(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/students")
    assert response.status_code == 401
