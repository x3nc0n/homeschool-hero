from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import get_db
from backend.models import (
    CurriculumLesson,
    CurriculumPackage,
    CurriculumUnit,
    LessonResource,
    Resource,
    ResourceType,
    SchoolYear,
    Subject,
)
from backend.schemas.curriculum import (
    CloneCurriculumPackageRequest,
    CurriculumLessonCreate,
    CurriculumLessonRead,
    CurriculumLessonUpdate,
    CurriculumPackageCreate,
    CurriculumPackageDetail,
    CurriculumPackageRead,
    CurriculumPackageUpdate,
    CurriculumUnitCreate,
    CurriculumUnitRead,
    CurriculumUnitUpdate,
    ResourceRead,
    ResourceUpdate,
    ResourceUpsert,
)
from backend.security import AuthSession, get_family_record
from backend.services.authorization import Capability, require_capabilities
from backend.validation import sanitize_filename

router = APIRouter(tags=['curriculum'])


def _package_options():
    return (
        selectinload(CurriculumPackage.units)
        .selectinload(CurriculumUnit.lessons)
        .selectinload(CurriculumLesson.resources),
    )


async def _ensure_unique_package_name(
    db: AsyncSession,
    *,
    family_id: int,
    school_year_id: int,
    name: str,
    current_package_id: int | None = None,
) -> None:
    stmt = select(CurriculumPackage).where(
        CurriculumPackage.family_id == family_id,
        CurriculumPackage.school_year_id == school_year_id,
        CurriculumPackage.name == name,
    )
    if current_package_id is not None:
        stmt = stmt.where(CurriculumPackage.id != current_package_id)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Curriculum package already exists')


async def _get_package_or_404(db: AsyncSession, package_id: int, family_id: int) -> CurriculumPackage:
    package = await get_family_record(db, CurriculumPackage, package_id, family_id, options=_package_options())
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Curriculum package not found')
    return package


async def _get_unit_or_404(db: AsyncSession, unit_id: int, family_id: int) -> CurriculumUnit:
    stmt = (
        select(CurriculumUnit)
        .options(selectinload(CurriculumUnit.lessons).selectinload(CurriculumLesson.resources), selectinload(CurriculumUnit.package))
        .join(CurriculumPackage, CurriculumPackage.id == CurriculumUnit.package_id)
        .where(CurriculumUnit.id == unit_id, CurriculumPackage.family_id == family_id)
    )
    unit = (await db.execute(stmt)).scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Curriculum unit not found')
    return unit


async def _get_lesson_or_404(db: AsyncSession, lesson_id: int, family_id: int) -> CurriculumLesson:
    stmt = (
        select(CurriculumLesson)
        .options(
            selectinload(CurriculumLesson.resources),
            selectinload(CurriculumLesson.unit).selectinload(CurriculumUnit.package),
        )
        .join(CurriculumUnit, CurriculumUnit.id == CurriculumLesson.unit_id)
        .join(CurriculumPackage, CurriculumPackage.id == CurriculumUnit.package_id)
        .where(CurriculumLesson.id == lesson_id, CurriculumPackage.family_id == family_id)
    )
    lesson = (await db.execute(stmt)).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Curriculum lesson not found')
    return lesson


async def _get_resource_or_404(db: AsyncSession, resource_id: int, family_id: int) -> Resource:
    resource = await get_family_record(db, Resource, resource_id, family_id, options=(selectinload(Resource.lessons),))
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Resource not found')
    return resource


async def _ensure_package_dependencies(
    db: AsyncSession,
    *,
    family_id: int,
    school_year_id: int,
    subject_id: int,
) -> None:
    if not await get_family_record(db, SchoolYear, school_year_id, family_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='School year not found')
    if not await get_family_record(db, Subject, subject_id, family_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subject not found')


async def _parse_request_json(request: Request) -> dict:
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid JSON payload') from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid request payload')
    return payload


def _parse_json_field(value: object, *, field_name: str, default: object) -> object:
    if value is None or value == '':
        return default
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Invalid {field_name} value')
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Invalid {field_name} JSON') from exc


async def _parse_resource_create_payload(request: Request) -> tuple[ResourceUpsert, object | None]:
    content_type = request.headers.get('content-type', '').lower()
    if 'multipart/form-data' in content_type:
        form = await request.form()
        payload = {
            'name': form.get('name'),
            'description': form.get('description'),
            'resource_type': form.get('resource_type'),
            'url': form.get('url'),
            'tags': _parse_json_field(form.get('tags'), field_name='tags', default=[]),
            'metadata': _parse_json_field(form.get('metadata'), field_name='metadata', default={}),
        }
        return ResourceUpsert.model_validate(payload), form.get('file')
    return ResourceUpsert.model_validate(await _parse_request_json(request)), None


def _validate_resource_file(resource_type: ResourceType, file_obj: object | None) -> None:
    if resource_type == ResourceType.file and file_obj is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='File resources require an uploaded file')
    if resource_type != ResourceType.file and file_obj is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only file resources can include uploads')


async def _store_resource_file(file_obj: object) -> tuple[str, str]:
    filename = getattr(file_obj, 'filename', None)
    content_type = (getattr(file_obj, 'content_type', None) or '').lower()
    safe_name = sanitize_filename(filename or '')
    suffix = Path(safe_name).suffix.lower()
    expected_mime, _ = mimetypes.guess_type(safe_name)
    effective_type = (content_type or expected_mime or 'application/octet-stream').lower()
    if effective_type not in settings.upload_allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported file type')
    if expected_mime and expected_mime.lower() not in settings.upload_allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported file type')
    contents = await file_obj.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is empty')
    if len(contents) > settings.upload_max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='Uploaded file exceeds size limit')
    resource_dir = Path(settings.upload_dir) / 'resources'
    resource_dir.mkdir(parents=True, exist_ok=True)
    destination = resource_dir / f'{uuid4().hex}{suffix}'
    destination.write_bytes(contents)
    return str(destination), effective_type


def _remove_resource_file(file_path: str | None) -> None:
    if not file_path:
        return
    path = Path(file_path)
    if path.exists() and path.is_file():
        path.unlink()


@router.get('/curriculum/packages', response_model=list[CurriculumPackageDetail])
async def list_curriculum_packages(
    school_year_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view curriculum packages')),
) -> list[CurriculumPackage]:
    stmt = select(CurriculumPackage).options(*_package_options()).where(CurriculumPackage.family_id == auth.family_id)
    if school_year_id is not None:
        stmt = stmt.where(CurriculumPackage.school_year_id == school_year_id)
    stmt = stmt.order_by(CurriculumPackage.school_year_id, CurriculumPackage.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post('/curriculum/packages', response_model=CurriculumPackageRead, status_code=status.HTTP_201_CREATED)
async def create_curriculum_package(
    payload: CurriculumPackageCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage curriculum packages')),
) -> CurriculumPackage:
    await _ensure_package_dependencies(
        db,
        family_id=auth.family_id,
        school_year_id=payload.school_year_id,
        subject_id=payload.subject_id,
    )
    await _ensure_unique_package_name(
        db, family_id=auth.family_id, school_year_id=payload.school_year_id, name=payload.name
    )
    package = CurriculumPackage(
        family_id=auth.family_id,
        school_year_id=payload.school_year_id,
        name=payload.name,
        description=payload.description,
        subject_id=payload.subject_id,
        created_by_user_id=auth.user_id,
    )
    db.add(package)
    await db.commit()
    await db.refresh(package)
    return package


@router.get('/curriculum/packages/{package_id}', response_model=CurriculumPackageDetail)
async def get_curriculum_package(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view curriculum packages')),
) -> CurriculumPackage:
    return await _get_package_or_404(db, package_id, auth.family_id)


@router.put('/curriculum/packages/{package_id}', response_model=CurriculumPackageRead)
async def update_curriculum_package(
    package_id: int,
    payload: CurriculumPackageUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage curriculum packages')),
) -> CurriculumPackage:
    package = await _get_package_or_404(db, package_id, auth.family_id)
    await _ensure_package_dependencies(
        db,
        family_id=auth.family_id,
        school_year_id=payload.school_year_id,
        subject_id=payload.subject_id,
    )
    await _ensure_unique_package_name(
        db,
        family_id=auth.family_id,
        school_year_id=payload.school_year_id,
        name=payload.name,
        current_package_id=package_id,
    )
    package.school_year_id = payload.school_year_id
    package.name = payload.name
    package.description = payload.description
    package.subject_id = payload.subject_id
    await db.commit()
    await db.refresh(package)
    return package


@router.delete('/curriculum/packages/{package_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_curriculum_package(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage curriculum packages')),
) -> None:
    package = await _get_package_or_404(db, package_id, auth.family_id)
    await db.delete(package)
    await db.commit()


@router.post('/curriculum/packages/{package_id}/clone', response_model=CurriculumPackageDetail, status_code=status.HTTP_201_CREATED)
async def clone_curriculum_package(
    package_id: int,
    payload: CloneCurriculumPackageRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='clone curriculum packages')),
) -> CurriculumPackage:
    source = await _get_package_or_404(db, package_id, auth.family_id)
    target_year = await get_family_record(db, SchoolYear, payload.target_school_year_id, auth.family_id)
    if not target_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Target school year not found')

    clone_name = payload.name or f'{source.name} ({target_year.name})'
    await _ensure_unique_package_name(
        db,
        family_id=auth.family_id,
        school_year_id=payload.target_school_year_id,
        name=clone_name,
    )
    cloned_package = CurriculumPackage(
        family_id=auth.family_id,
        school_year_id=payload.target_school_year_id,
        name=clone_name,
        description=source.description,
        subject_id=source.subject_id,
        created_by_user_id=auth.user_id,
    )
    db.add(cloned_package)
    await db.flush()

    for unit in source.units:
        cloned_unit = CurriculumUnit(
            package_id=cloned_package.id,
            name=unit.name,
            description=unit.description,
            sequence_order=unit.sequence_order,
            standards_tags=list(unit.standards_tags or []),
        )
        db.add(cloned_unit)
        await db.flush()
        for lesson in unit.lessons:
            cloned_lesson = CurriculumLesson(
                unit_id=cloned_unit.id,
                name=lesson.name,
                description=lesson.description,
                sequence_order=lesson.sequence_order,
                estimated_duration_minutes=lesson.estimated_duration_minutes,
                standards_tags=list(lesson.standards_tags or []),
            )
            db.add(cloned_lesson)
            await db.flush()
            for resource in lesson.resources:
                db.add(LessonResource(lesson_id=cloned_lesson.id, resource_id=resource.id))

    await db.commit()
    return await _get_package_or_404(db, cloned_package.id, auth.family_id)


@router.get('/curriculum/units', response_model=list[CurriculumUnitRead])
async def list_curriculum_units(
    package_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view curriculum units')),
) -> list[CurriculumUnit]:
    await _get_package_or_404(db, package_id, auth.family_id)
    stmt = (
        select(CurriculumUnit)
        .options(selectinload(CurriculumUnit.lessons).selectinload(CurriculumLesson.resources))
        .where(CurriculumUnit.package_id == package_id)
        .order_by(CurriculumUnit.sequence_order, CurriculumUnit.id)
    )
    return list((await db.execute(stmt)).scalars().all())


@router.post('/curriculum/units', response_model=CurriculumUnitRead, status_code=status.HTTP_201_CREATED)
async def create_curriculum_unit(
    payload: CurriculumUnitCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage curriculum units')),
) -> CurriculumUnit:
    await _get_package_or_404(db, payload.package_id, auth.family_id)
    unit = CurriculumUnit(
        package_id=payload.package_id,
        name=payload.name,
        description=payload.description,
        sequence_order=payload.sequence_order,
        standards_tags=payload.standards_tags,
    )
    db.add(unit)
    await db.commit()
    return await _get_unit_or_404(db, unit.id, auth.family_id)


@router.get('/curriculum/units/{unit_id}', response_model=CurriculumUnitRead)
async def get_curriculum_unit(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view curriculum units')),
) -> CurriculumUnit:
    return await _get_unit_or_404(db, unit_id, auth.family_id)


@router.put('/curriculum/units/{unit_id}', response_model=CurriculumUnitRead)
async def update_curriculum_unit(
    unit_id: int,
    payload: CurriculumUnitUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage curriculum units')),
) -> CurriculumUnit:
    unit = await _get_unit_or_404(db, unit_id, auth.family_id)
    unit.name = payload.name
    unit.description = payload.description
    unit.sequence_order = payload.sequence_order
    unit.standards_tags = payload.standards_tags
    await db.commit()
    return await _get_unit_or_404(db, unit_id, auth.family_id)


@router.delete('/curriculum/units/{unit_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_curriculum_unit(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage curriculum units')),
) -> None:
    unit = await _get_unit_or_404(db, unit_id, auth.family_id)
    await db.delete(unit)
    await db.commit()


@router.get('/curriculum/lessons', response_model=list[CurriculumLessonRead])
async def list_curriculum_lessons(
    unit_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view curriculum lessons')),
) -> list[CurriculumLesson]:
    await _get_unit_or_404(db, unit_id, auth.family_id)
    stmt = (
        select(CurriculumLesson)
        .options(selectinload(CurriculumLesson.resources))
        .where(CurriculumLesson.unit_id == unit_id)
        .order_by(CurriculumLesson.sequence_order, CurriculumLesson.id)
    )
    return list((await db.execute(stmt)).scalars().all())


@router.post('/curriculum/lessons', response_model=CurriculumLessonRead, status_code=status.HTTP_201_CREATED)
async def create_curriculum_lesson(
    payload: CurriculumLessonCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage curriculum lessons')),
) -> CurriculumLesson:
    await _get_unit_or_404(db, payload.unit_id, auth.family_id)
    lesson = CurriculumLesson(
        unit_id=payload.unit_id,
        name=payload.name,
        description=payload.description,
        sequence_order=payload.sequence_order,
        estimated_duration_minutes=payload.estimated_duration_minutes,
        standards_tags=payload.standards_tags,
    )
    db.add(lesson)
    await db.commit()
    return await _get_lesson_or_404(db, lesson.id, auth.family_id)


@router.get('/curriculum/lessons/{lesson_id}', response_model=CurriculumLessonRead)
async def get_curriculum_lesson(
    lesson_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view curriculum lessons')),
) -> CurriculumLesson:
    return await _get_lesson_or_404(db, lesson_id, auth.family_id)


@router.put('/curriculum/lessons/{lesson_id}', response_model=CurriculumLessonRead)
async def update_curriculum_lesson(
    lesson_id: int,
    payload: CurriculumLessonUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage curriculum lessons')),
) -> CurriculumLesson:
    lesson = await _get_lesson_or_404(db, lesson_id, auth.family_id)
    lesson.name = payload.name
    lesson.description = payload.description
    lesson.sequence_order = payload.sequence_order
    lesson.estimated_duration_minutes = payload.estimated_duration_minutes
    lesson.standards_tags = payload.standards_tags
    await db.commit()
    return await _get_lesson_or_404(db, lesson_id, auth.family_id)


@router.delete('/curriculum/lessons/{lesson_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_curriculum_lesson(
    lesson_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage curriculum lessons')),
) -> None:
    lesson = await _get_lesson_or_404(db, lesson_id, auth.family_id)
    await db.delete(lesson)
    await db.commit()


@router.post('/curriculum/lessons/{lesson_id}/resources/{resource_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def link_resource_to_lesson(
    lesson_id: int,
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='link resources to lessons')),
) -> None:
    lesson = await _get_lesson_or_404(db, lesson_id, auth.family_id)
    resource = await _get_resource_or_404(db, resource_id, auth.family_id)
    if any(existing.id == resource.id for existing in lesson.resources):
        return
    lesson.resources.append(resource)
    await db.commit()


@router.delete('/curriculum/lessons/{lesson_id}/resources/{resource_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def unlink_resource_from_lesson(
    lesson_id: int,
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(
        require_capabilities(Capability.manage_curriculum, action='unlink resources from lessons')
    ),
) -> None:
    lesson = await _get_lesson_or_404(db, lesson_id, auth.family_id)
    lesson.resources = [resource for resource in lesson.resources if resource.id != resource_id]
    await db.commit()


@router.get('/resources', response_model=list[ResourceRead])
async def list_resources(
    search: str | None = Query(default=None, max_length=160),
    resource_type: ResourceType | None = Query(default=None),
    tag: str | None = Query(default=None, max_length=120),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view resources')),
) -> list[Resource]:
    stmt = (
        select(Resource)
        .options(selectinload(Resource.lessons))
        .where(Resource.family_id == auth.family_id)
        .order_by(Resource.name)
    )
    resources = list((await db.execute(stmt)).scalars().all())
    normalized_search = search.strip().lower() if search else None
    normalized_tag = tag.strip().lower() if tag else None
    filtered: list[Resource] = []
    for resource in resources:
        if resource_type is not None and resource.resource_type != resource_type:
            continue
        if normalized_search and normalized_search not in f'{resource.name} {resource.description or ""}'.lower():
            continue
        if normalized_tag and normalized_tag not in {item.lower() for item in resource.tags or []}:
            continue
        filtered.append(resource)
    return filtered


@router.post('/resources', response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
async def create_resource(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage resources')),
) -> Resource:
    payload, file_obj = await _parse_resource_create_payload(request)
    _validate_resource_file(payload.resource_type, file_obj)

    file_path = None
    if file_obj is not None:
        file_path, _ = await _store_resource_file(file_obj)

    if payload.resource_type == ResourceType.link and not payload.url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Link resources require a URL')
    if payload.resource_type != ResourceType.link:
        payload.url = None

    resource = Resource(
        family_id=auth.family_id,
        name=payload.name,
        description=payload.description,
        resource_type=payload.resource_type,
        file_path=file_path,
        url=payload.url,
        tags=payload.tags,
        resource_metadata=payload.metadata,
        created_by_user_id=auth.user_id,
    )
    db.add(resource)
    await db.commit()
    return await _get_resource_or_404(db, resource.id, auth.family_id)


@router.get('/resources/{resource_id}', response_model=ResourceRead)
async def get_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view resources')),
) -> Resource:
    return await _get_resource_or_404(db, resource_id, auth.family_id)


@router.put('/resources/{resource_id}', response_model=ResourceRead)
async def update_resource(
    resource_id: int,
    payload: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage resources')),
) -> Resource:
    resource = await _get_resource_or_404(db, resource_id, auth.family_id)
    if payload.resource_type == ResourceType.link and not payload.url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Link resources require a URL')
    if payload.resource_type == ResourceType.file and not resource.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='File resources must be created with an uploaded file',
        )
    resource.name = payload.name
    resource.description = payload.description
    resource.resource_type = payload.resource_type
    resource.url = payload.url if payload.resource_type == ResourceType.link else None
    resource.tags = payload.tags
    resource.resource_metadata = payload.metadata
    await db.commit()
    return await _get_resource_or_404(db, resource_id, auth.family_id)


@router.delete('/resources/{resource_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='manage resources')),
) -> None:
    resource = await _get_resource_or_404(db, resource_id, auth.family_id)
    file_path = resource.file_path
    await db.delete(resource)
    await db.commit()
    _remove_resource_file(file_path)
