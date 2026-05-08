from __future__ import annotations

import inspect
from typing import Any

import pytest
from httpx import AsyncClient

from tests.contracts import VALIDATION_STATUS_CODES


def resolve_attr(module: Any, candidates: tuple[str, ...], *, label: str) -> Any:
    for candidate in candidates:
        value = getattr(module, candidate, None)
        if value is not None:
            return value
    pytest.fail(f"{label} contract is missing. Expected one of: {', '.join(candidates)}")


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def assert_validation_error(response) -> None:
    assert response.status_code in VALIDATION_STATUS_CODES, response.text


async def update_resource(client: AsyncClient, path: str, payload: dict[str, Any]):
    response = await client.put(path, json=payload)
    if response.status_code in {404, 405}:
        response = await client.patch(path, json=payload)
    return response


def response_id(payload: dict[str, Any]) -> Any:
    for key in ("id", "student_id", "subject_id", "assignment_id", "submission_id", "grade_id", "quiz_id", "job_id"):
        if key in payload:
            return payload[key]
    pytest.fail(f"Response payload does not expose an id field: {payload}")


def require_route(app: Any, method: str, path: str) -> None:
    target = (method.upper(), path)
    available = {
        (allowed_method, route.path)
        for route in getattr(app, "routes", [])
        for allowed_method in (getattr(route, "methods", None) or set())
    }
    if target not in available:
        pytest.skip(f"Route not implemented yet: {method.upper()} {path}")
