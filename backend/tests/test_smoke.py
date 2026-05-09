from fastapi.testclient import TestClient


def test_health_endpoint(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["required"]["database"] == "ok"
    assert "capabilities" in payload
    assert "ai_grading" in payload["capabilities"]


def test_health_endpoint_reports_required_failures(app, monkeypatch) -> None:
    monkeypatch.setattr("backend.main._check_database_health", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "required_failure"
    assert payload["required"]["database"] == "failed"
    assert payload["required_failures"]["database"] == "db down"


def test_capabilities_endpoint_returns_current_flags(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "capabilities" in payload
    assert {"ai_grading", "email", "backup", "ocr"} <= set(payload["capabilities"])


def test_auth_protects_api_routes(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/students")
    assert response.status_code == 401
