from __future__ import annotations

import importlib
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from tests.contracts import (
    ASSIGNMENTS,
    AUTH,
    GRADES,
    QUIZZES,
    STUDENTS,
    SUBJECTS,
    SUBMISSIONS,
    UPLOADS_DIR,
    assignment_payload,
    bootstrap_payload,
    grade_payload,
    quiz_attempt_payload,
    quiz_payload,
    student_payload,
    subject_payload,
)
from tests.helpers import response_id

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DB_DIR = BACKEND_ROOT / '.pytest-state'

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _set_test_environment() -> None:
    DB_DIR.mkdir(exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    sqlite_url = f"sqlite+aiosqlite:///{(DB_DIR / 'test.db').resolve().as_posix()}"
    os.environ['APP_ENV'] = 'test'
    os.environ['TESTING'] = '1'
    os.environ['DATABASE_URL'] = sqlite_url
    os.environ['BOOTSTRAP_OWNER_EMAIL'] = 'owner@example.com'
    os.environ['BOOTSTRAP_OWNER_DISPLAY_NAME'] = 'Parent User'
    os.environ['BOOTSTRAP_FAMILY_NAME'] = 'Test Family'
    os.environ['BOOTSTRAP_TIMEZONE'] = 'UTC'
    os.environ['BOOTSTRAP_GRADING_SCALE'] = 'letter'
    os.environ['FAMILY_PASSWORD'] = 'legacy-password'
    os.environ['CONFIDENCE_THRESHOLD'] = '0.8'
    os.environ['UPLOAD_DIR'] = str(UPLOADS_DIR.resolve())


_set_test_environment()


def _clear_uploads_dir() -> None:
    if not UPLOADS_DIR.exists():
        return
    for child in UPLOADS_DIR.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _import_optional_module(*names: str):
    for name in names:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError as exc:
            missing = exc.name or ''
            root_name = name.split('.')[0]
            if missing in {name, root_name}:
                continue
            raise
    pytest.skip(
        "Backend implementation is not available yet; API contract tests are staged for Ray's backend.",
        allow_module_level=True,
    )


@pytest.fixture(scope='session', autouse=True)
def test_environment():
    _set_test_environment()
    yield


@pytest.fixture(scope='session')
def backend_module(test_environment):
    return _import_optional_module('backend.main', 'main')


@pytest_asyncio.fixture(scope='session')
async def database_schema(test_environment):
    database_module = _import_optional_module('backend.database')
    models_module = _import_optional_module('backend.models')
    async with database_module.engine.begin() as connection:
        await connection.run_sync(models_module.Base.metadata.create_all)
    yield
    async with database_module.engine.begin() as connection:
        await connection.run_sync(models_module.Base.metadata.drop_all)
    await database_module.engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def reset_database(database_schema):
    database_module = _import_optional_module('backend.database')
    models_module = _import_optional_module('backend.models')
    async with database_module.AsyncSessionLocal() as session:
        for table in reversed(models_module.Base.metadata.sorted_tables):
            await session.execute(delete(table))
        await session.commit()
    _clear_uploads_dir()
    yield


@pytest.fixture
def app(backend_module, database_schema):
    app_factory = getattr(backend_module, 'create_app', None)
    if callable(app_factory):
        return app_factory()
    app = getattr(backend_module, 'app', None)
    if app is None:
        pytest.fail('Expected FastAPI app on main.app or main.create_app()')
    return app


@pytest_asyncio.fixture
async def async_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        yield client


@pytest_asyncio.fixture
async def secondary_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        yield client


@pytest_asyncio.fixture
async def authorized_client(async_client: AsyncClient):
    response = await async_client.post(AUTH['register'], json=bootstrap_payload())
    assert response.status_code == 201, response.text
    return async_client


@pytest_asyncio.fixture
async def create_family_user(database_schema):
    database_module = _import_optional_module('backend.database')
    models_module = _import_optional_module('backend.models')
    security_module = _import_optional_module('backend.security')

    async def _create(*, family_name: str, email: str, password: str, display_name: str = 'Secondary User'):
        async with database_module.AsyncSessionLocal() as session:
            family = models_module.Family(name=family_name, settings={'timezone': 'UTC', 'grading_scale': 'letter'})
            user = models_module.User(
                email=email,
                display_name=display_name,
                password_hash=security_module.hash_password(password),
                is_active=True,
            )
            now = datetime.now(timezone.utc)
            membership = models_module.FamilyMembership(
                user=user,
                family=family,
                role=models_module.FamilyRole.parent,
                is_owner=True,
                invited_at=now,
                accepted_at=now,
            )
            family_settings = models_module.FamilySettings(family=family, timezone='UTC', grading_scale='letter')
            session.add_all([family, user, membership, family_settings])
            await session.commit()
            return {'family_id': family.id, 'user_id': user.id, 'email': user.email, 'password': password}

    return _create


@pytest_asyncio.fixture
async def seeded_subject(authorized_client: AsyncClient):
    response = await authorized_client.post(SUBJECTS['collection'], json=subject_payload())
    assert response.status_code in {200, 201}, response.text
    return response.json()


@pytest_asyncio.fixture
async def seeded_student(authorized_client: AsyncClient):
    response = await authorized_client.post(STUDENTS['collection'], json=student_payload())
    assert response.status_code in {200, 201}, response.text
    return response.json()


@pytest_asyncio.fixture
async def seeded_assignment(authorized_client: AsyncClient, seeded_subject: dict[str, Any]):
    response = await authorized_client.post(
        ASSIGNMENTS['collection'],
        json=assignment_payload(response_id(seeded_subject)),
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()


@pytest_asyncio.fixture
async def seeded_submission(
    authorized_client: AsyncClient,
    seeded_assignment: dict[str, Any],
    seeded_student: dict[str, Any],
):
    response = await authorized_client.post(
        SUBMISSIONS['collection'],
        data={
            'assignment_id': str(response_id(seeded_assignment)),
            'student_id': str(response_id(seeded_student)),
        },
        files={'file': ('fractions.txt', b'fraction work', 'text/plain')},
    )
    assert response.status_code in {200, 201, 202}, response.text
    return response.json()


@pytest_asyncio.fixture
async def seeded_grade(
    authorized_client: AsyncClient,
    seeded_submission: dict[str, Any],
    seeded_student: dict[str, Any],
):
    response = await authorized_client.post(
        GRADES['collection'],
        json=grade_payload(response_id(seeded_submission), response_id(seeded_student)),
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()


@pytest_asyncio.fixture
async def seeded_quiz(authorized_client: AsyncClient, seeded_subject: dict[str, Any]):
    response = await authorized_client.post(
        QUIZZES['collection'],
        json=quiz_payload(response_id(seeded_subject)),
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()


@pytest.fixture
def quiz_attempt_body(seeded_student: dict[str, Any]):
    return quiz_attempt_payload(response_id(seeded_student))
