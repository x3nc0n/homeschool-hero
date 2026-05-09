import pytest
from sqlalchemy import func, select

import backend.main as main_module
from backend.database import AsyncSessionLocal
from backend.models import (
    Assignment,
    AttendanceRecord,
    CurriculumPackage,
    Family,
    FamilySettings,
    GradingPeriod,
    SchoolYear,
    Student,
    Subject,
    Term,
    User,
)
from backend.seed_demo import seed_demo_data


@pytest.mark.asyncio
async def test_seed_demo_data_populates_empty_database() -> None:
    async with AsyncSessionLocal() as session:
        seeded = await seed_demo_data(session)

    assert seeded is True

    async with AsyncSessionLocal() as session:
        family = (await session.execute(select(Family))).scalar_one()
        assert family.name == 'Demo Family'

        family_settings = await session.get(FamilySettings, family.id)
        assert family_settings is not None
        assert family_settings.timezone == 'America/Chicago'
        assert family_settings.state_code == 'OK'
        assert family_settings.grading_scale == 'letter'

        user = (
            await session.execute(select(User).where(User.email == 'demo@example.com'))
        ).scalar_one()
        assert user.display_name == 'Demo Parent'

        assert (await session.execute(select(func.count()).select_from(Student))).scalar_one() == 13
        subject_count = (await session.execute(select(func.count()).select_from(Subject))).scalar_one()
        assert subject_count == 98
        assert (await session.execute(select(func.count()).select_from(CurriculumPackage))).scalar_one() == subject_count
        assert (await session.execute(select(func.count()).select_from(Assignment))).scalar_one() == 130
        assert (await session.execute(select(func.count()).select_from(AttendanceRecord))).scalar_one() == 780
        assert (await session.execute(select(func.count()).select_from(SchoolYear))).scalar_one() == 1
        assert (await session.execute(select(func.count()).select_from(Term))).scalar_one() == 2
        assert (await session.execute(select(func.count()).select_from(GradingPeriod))).scalar_one() == 4


@pytest.mark.asyncio
async def test_seed_demo_data_is_idempotent() -> None:
    async with AsyncSessionLocal() as session:
        assert await seed_demo_data(session) is True

    async with AsyncSessionLocal() as session:
        assert await seed_demo_data(session) is False

    async with AsyncSessionLocal() as session:
        assert (await session.execute(select(func.count()).select_from(Family))).scalar_one() == 1


@pytest.mark.asyncio
async def test_maybe_seed_demo_data_respects_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    async def fake_seed(session) -> bool:
        calls.append(True)
        return True

    monkeypatch.setattr(main_module, 'seed_demo_data', fake_seed)
    monkeypatch.setattr(main_module.settings, 'demo_mode', False, raising=False)
    assert await main_module.maybe_seed_demo_data() is False
    assert calls == []

    monkeypatch.setattr(main_module.settings, 'demo_mode', True, raising=False)
    assert await main_module.maybe_seed_demo_data() is True
    assert calls == [True]
