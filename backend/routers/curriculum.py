from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import get_db
from backend.i18n import build_error_payload
from backend.models import (
    Assignment,
    AssignmentCategory,
    AssignmentStatus,
    CurriculumLesson,
    CurriculumPackage,
    CurriculumUnit,
    ImportedCurriculum,
    ImportedCurriculumLesson,
    ImportedCurriculumSubject,
    ImportedCurriculumUnit,
    LessonResource,
    Resource,
    ResourceType,
    SchoolYear,
    Subject,
)
from backend.schemas.curriculum import (
    CurriculumAIImportConfirmRequest,
    CurriculumAIImportRead,
    CloneCurriculumPackageRequest,
    CurriculumImportActivationRead,
    CurriculumImportActivationRequest,
    CurriculumImportDocument,
    CurriculumImportRead,
    CurriculumImportSummaryRead,
    CurriculumSourceRead,
    CurriculumSourceSearchRead,
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
from backend.services.authorization import AppRole, Capability, require_any_role, require_capabilities, require_teacher
from backend.services.curriculum_ai_import import (
    AIImportError,
    AIImportUnavailable,
    get_ai_curriculum_import_service,
)
from backend.services.curriculum_imports import create_imported_curriculum, imported_curriculum_load_options
from backend.services.curriculum_sources import (
    CurriculumSourceError,
    CurriculumSourceUnavailable,
    get_curriculum_source,
    list_curriculum_sources,
)
from backend.validation import sanitize_filename

router = APIRouter(tags=['curriculum'])
logger = logging.getLogger(__name__)

CURRICULUM_SOURCE_UNAVAILABLE_MESSAGE = 'Curriculum source is unavailable'
CURRICULUM_SOURCE_ERROR_MESSAGE = 'Curriculum source request failed'
AI_IMPORT_UNAVAILABLE_MESSAGE = 'AI curriculum import is unavailable'


def _package_options():
    return (
        selectinload(CurriculumPackage.units)
        .selectinload(CurriculumUnit.lessons)
        .selectinload(CurriculumLesson.resources),
    )


def _curriculum_import_options():
    return imported_curriculum_load_options()


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


async def _get_imported_curriculum_or_404(
    db: AsyncSession,
    curriculum_id: int,
    family_id: int,
) -> ImportedCurriculum:
    curriculum = await get_family_record(
        db,
        ImportedCurriculum,
        curriculum_id,
        family_id,
        options=_curriculum_import_options(),
    )
    if not curriculum:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Imported curriculum not found')
    return curriculum


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


async def _create_imported_curriculum_response(
    db: AsyncSession,
    *,
    auth: AuthSession,
    payload: CurriculumImportDocument,
) -> ImportedCurriculum:
    try:
        created = await create_imported_curriculum(
            db,
            family_id=auth.family_id,
            user_id=auth.user_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _get_imported_curriculum_or_404(db, created.id, auth.family_id)


async def _parse_ai_import_request(request: Request) -> tuple[object | None, str | None]:
    content_type = request.headers.get('content-type', '').lower()
    if 'multipart/form-data' in content_type:
        form = await request.form()
        upload = form.get('file')
        url = form.get('url')
    else:
        payload = await _parse_request_json(request)
        upload = None
        url = payload.get('url')
    normalized_url = url.strip() if isinstance(url, str) and url.strip() else None
    has_upload = upload is not None
    if has_upload == bool(normalized_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Provide exactly one source for AI import: either a file upload or a URL.',
        )
    return upload, normalized_url


def _curriculum_source_to_read(source) -> CurriculumSourceRead:
    availability = source.availability()
    return CurriculumSourceRead(
        source=source.source_id,
        name=source.display_name,
        description=source.description,
        enabled=availability.enabled,
        configuration_required=availability.configuration_required,
        detail=availability.detail,
    )


def _curriculum_source_search_to_read(search_page) -> CurriculumSourceSearchRead:
    return CurriculumSourceSearchRead(
        source=search_page.source,
        query=search_page.query,
        page=search_page.page,
        page_size=search_page.page_size,
        total_count=search_page.total_count,
        has_more=search_page.has_more,
        items=[
            {
                'item_id': item.id,
                'title': item.title,
                'description': item.description,
                'subjects': item.subjects,
                'grade_levels': item.grade_levels,
                'url': item.url,
                'image_url': item.image_url,
                'license_name': item.license_name,
                'metadata': item.metadata,
            }
            for item in search_page.items
        ],
    )


def _service_unavailable_response(request: Request, *, detail: str, code: str) -> JSONResponse:
    locale = getattr(request.state, 'locale', 'en')
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=build_error_payload(
            detail,
            locale=locale,
            requested_locale=request.headers.get('accept-language'),
            fallback_code=code,
            fallback_message=detail,
        ),
    )


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


def _truncate_name(value: str, *, max_length: int) -> str:
    return value if len(value) <= max_length else value[: max_length - 1].rstrip()


def _allocate_unique_name(base_name: str, existing_names: set[str], *, max_length: int) -> str:
    candidate = _truncate_name(base_name, max_length=max_length)
    if candidate not in existing_names:
        existing_names.add(candidate)
        return candidate
    counter = 2
    while True:
        suffix = f' ({counter})'
        trimmed = _truncate_name(base_name, max_length=max_length - len(suffix))
        candidate = f'{trimmed}{suffix}'
        if candidate not in existing_names:
            existing_names.add(candidate)
            return candidate
        counter += 1


def _package_name_for_import(curriculum: ImportedCurriculum, subject: ImportedCurriculumSubject) -> str:
    if curriculum.subject_count <= 1:
        return curriculum.name
    return _truncate_name(f'{curriculum.name} - {subject.name}', max_length=160)


def _merge_descriptions(*parts: str | None) -> str | None:
    normalized = [part.strip() for part in parts if isinstance(part, str) and part.strip()]
    if not normalized:
        return None
    return '\n\n'.join(normalized)


def _build_lesson_description(imported_lesson: ImportedCurriculumLesson) -> str | None:
    objectives = [objective.strip() for objective in imported_lesson.objectives if objective.strip()]
    objectives_block = None
    if objectives:
        objectives_block = 'Objectives:\n' + '\n'.join(f'- {objective}' for objective in objectives)
    return _merge_descriptions(imported_lesson.description, objectives_block)


def _resource_attachments_for_import(resources: list[Resource]) -> list[str]:
    attachments: list[str] = []
    for resource in resources:
        if resource.file_url:
            attachments.append(resource.file_url)
        elif resource.url:
            attachments.append(resource.url)
    return attachments


@router.get('/curriculum/schema')
async def get_curriculum_import_schema(
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view curriculum import schema')),
) -> dict[str, object]:
    del auth
    return CurriculumImportDocument.model_json_schema()


@router.get('/curriculum/sources', response_model=list[CurriculumSourceRead])
async def list_curriculum_source_connectors(
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view curriculum sources')),
) -> list[CurriculumSourceRead]:
    del auth
    return [_curriculum_source_to_read(source) for source in list_curriculum_sources()]


@router.get('/curriculum/sources/{source_id}/search', response_model=CurriculumSourceSearchRead)
async def search_curriculum_source(
    request: Request,
    source_id: str,
    q: str = Query(min_length=1, max_length=200),
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=10, ge=1, le=50),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='search curriculum sources')),
) -> CurriculumSourceSearchRead:
    del auth
    source = get_curriculum_source(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Curriculum source not found')
    availability = source.availability()
    if not availability.enabled:
        return _service_unavailable_response(
            request,
            detail=availability.detail or CURRICULUM_SOURCE_UNAVAILABLE_MESSAGE,
            code='curriculum_source_unavailable',
        )
    try:
        search_page = await source.search(q, page=page, page_size=page_size)
    except CurriculumSourceUnavailable:
        logger.exception('Curriculum source search unavailable.')
        return _service_unavailable_response(
            request,
            detail=CURRICULUM_SOURCE_UNAVAILABLE_MESSAGE,
            code='curriculum_source_unavailable',
        )
    except CurriculumSourceError:
        logger.exception('Curriculum source search failed.')
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=CURRICULUM_SOURCE_ERROR_MESSAGE) from None
    return _curriculum_source_search_to_read(search_page)


@router.post('/curriculum/sources/{source_id}/import/{item_id}', response_model=CurriculumImportRead, status_code=status.HTTP_201_CREATED)
async def import_curriculum_from_source(
    request: Request,
    source_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='import curriculum from source')),
) -> ImportedCurriculum:
    source = get_curriculum_source(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Curriculum source not found')
    availability = source.availability()
    if not availability.enabled:
        return _service_unavailable_response(
            request,
            detail=availability.detail or CURRICULUM_SOURCE_UNAVAILABLE_MESSAGE,
            code='curriculum_source_unavailable',
        )
    try:
        raw_data = await source.fetch(item_id)
        payload = source.convert_to_standard_format(raw_data)
    except CurriculumSourceUnavailable:
        logger.exception('Curriculum source import unavailable.')
        return _service_unavailable_response(
            request,
            detail=CURRICULUM_SOURCE_UNAVAILABLE_MESSAGE,
            code='curriculum_source_unavailable',
        )
    except CurriculumSourceError:
        logger.exception('Curriculum source import failed.')
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=CURRICULUM_SOURCE_ERROR_MESSAGE) from None
    return await _create_imported_curriculum_response(db, auth=auth, payload=payload)


@router.post('/curriculum/ai-import', response_model=CurriculumAIImportRead)
async def draft_curriculum_from_ai_import(
    request: Request,
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='draft AI curriculum import')),
) -> CurriculumAIImportRead:
    del auth
    upload, url = await _parse_ai_import_request(request)
    service = get_ai_curriculum_import_service()
    try:
        if upload is not None:
            draft, extracted = await service.build_draft_from_upload(upload)
        else:
            draft, extracted = await service.build_draft_from_url(url or '')
    except AIImportUnavailable:
        logger.exception('AI curriculum import is unavailable.')
        return _service_unavailable_response(request, detail=AI_IMPORT_UNAVAILABLE_MESSAGE, code='ai_import_unavailable')
    except AIImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CurriculumAIImportRead(
        draft=draft,
        source_kind=extracted.source_kind,
        source_name=extracted.source_name,
        warnings=extracted.warnings or [],
    )


@router.post('/curriculum/ai-import/confirm', response_model=CurriculumImportRead, status_code=status.HTTP_201_CREATED)
async def confirm_ai_curriculum_import(
    payload: CurriculumAIImportConfirmRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='confirm AI curriculum import')),
) -> ImportedCurriculum:
    return await _create_imported_curriculum_response(db, auth=auth, payload=payload.draft)


@router.post('/curriculum/import', response_model=CurriculumImportRead, status_code=status.HTTP_201_CREATED)
async def import_curriculum(
    payload: CurriculumImportDocument,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='import curriculum')),
) -> ImportedCurriculum:
    return await _create_imported_curriculum_response(db, auth=auth, payload=payload)


@router.get('/curriculum', response_model=list[CurriculumImportSummaryRead])
async def list_imported_curricula(
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view imported curricula')),
) -> list[ImportedCurriculum]:
    stmt = (
        select(ImportedCurriculum)
        .options(*_curriculum_import_options())
        .where(ImportedCurriculum.family_id == auth.family_id)
        .order_by(ImportedCurriculum.created_at.desc(), ImportedCurriculum.id.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


@router.get('/curriculum/{curriculum_id:int}', response_model=CurriculumImportRead)
async def get_imported_curriculum(
    curriculum_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.read_curriculum, action='view imported curricula')),
) -> ImportedCurriculum:
    return await _get_imported_curriculum_or_404(db, curriculum_id, auth.family_id)


@router.post('/curriculum/{curriculum_id:int}/activate', response_model=CurriculumImportActivationRead)
async def activate_imported_curriculum(
    curriculum_id: int,
    payload: CurriculumImportActivationRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='activate imported curriculum')),
) -> CurriculumImportActivationRead:
    curriculum = await _get_imported_curriculum_or_404(db, curriculum_id, auth.family_id)
    if curriculum.is_activated:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Imported curriculum has already been activated')

    school_year = await get_family_record(db, SchoolYear, payload.school_year_id, auth.family_id)
    if not school_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='School year not found')

    subject_ids = set(payload.subject_mappings.values())
    subject_records = {}
    if subject_ids:
        rows = (
            await db.execute(
                select(Subject).where(Subject.family_id == auth.family_id, Subject.id.in_(subject_ids)).order_by(Subject.name)
            )
        ).scalars().all()
        subject_records = {subject.id: subject for subject in rows}
        if len(subject_records) != len(subject_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='One or more mapped subjects were not found')

    imported_subject_ids = {subject.id for subject in curriculum.subjects}
    invalid_subject_ids = set(payload.subject_mappings) - imported_subject_ids
    if invalid_subject_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='One or more imported subject mappings were not found')

    existing_subjects = (
        await db.execute(select(Subject).where(Subject.family_id == auth.family_id).order_by(Subject.name))
    ).scalars().all()
    subjects_by_name = {subject.name: subject for subject in existing_subjects}
    existing_resource_names = {
        name for name in (await db.execute(select(Resource.name).where(Resource.family_id == auth.family_id))).scalars().all()
    }

    package_ids: list[int] = []
    activated_subject_ids: list[int] = []
    unit_ids: list[int] = []
    lesson_ids: list[int] = []
    resource_ids: list[int] = []
    assignment_ids: list[int] = []

    for imported_subject in curriculum.subjects:
        subject = subject_records.get(payload.subject_mappings.get(imported_subject.id))
        if subject is None:
            subject = subjects_by_name.get(imported_subject.name)
        if subject is None and payload.create_missing_subjects:
            subject = Subject(family_id=auth.family_id, name=imported_subject.name)
            db.add(subject)
            await db.flush()
            subjects_by_name[subject.name] = subject
        if subject is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Subject mapping is required for imported subject "{imported_subject.name}"',
            )

        package_name = _package_name_for_import(curriculum, imported_subject)
        await _ensure_unique_package_name(
            db,
            family_id=auth.family_id,
            school_year_id=school_year.id,
            name=package_name,
        )
        package = CurriculumPackage(
            family_id=auth.family_id,
            school_year_id=school_year.id,
            name=package_name,
            description=_merge_descriptions(curriculum.description, imported_subject.description),
            subject_id=subject.id,
            created_by_user_id=auth.user_id,
        )
        db.add(package)
        await db.flush()

        imported_subject.activated_subject_id = subject.id
        imported_subject.activated_package_id = package.id
        package_ids.append(package.id)
        activated_subject_ids.append(subject.id)

        for imported_unit in imported_subject.units:
            activated_unit = CurriculumUnit(
                package_id=package.id,
                name=imported_unit.name,
                description=imported_unit.description,
                sequence_order=imported_unit.sequence_order,
                standards_tags=imported_unit.standards_alignment or imported_subject.standards_alignment,
            )
            db.add(activated_unit)
            await db.flush()
            imported_unit.activated_curriculum_unit_id = activated_unit.id
            unit_ids.append(activated_unit.id)

            for imported_lesson in imported_unit.lessons:
                activated_lesson = CurriculumLesson(
                    unit_id=activated_unit.id,
                    name=imported_lesson.name,
                    description=_build_lesson_description(imported_lesson),
                    sequence_order=imported_lesson.sequence_order,
                    estimated_duration_minutes=imported_lesson.estimated_minutes,
                    standards_tags=imported_lesson.standards_alignment or imported_unit.standards_alignment,
                )
                db.add(activated_lesson)
                await db.flush()
                imported_lesson.activated_curriculum_lesson_id = activated_lesson.id
                lesson_ids.append(activated_lesson.id)

                created_resources: list[Resource] = []
                for resource_payload in imported_lesson.resources:
                    resource_name = _allocate_unique_name(
                        resource_payload.get('name') or f'{imported_lesson.name} resource',
                        existing_resource_names,
                        max_length=160,
                    )
                    resource = Resource(
                        family_id=auth.family_id,
                        name=resource_name,
                        description=resource_payload.get('description'),
                        resource_type=ResourceType.link if resource_payload.get('url') else ResourceType.note,
                        url=resource_payload.get('url'),
                        tags=list(resource_payload.get('tags') or []),
                        resource_metadata={
                            'source': curriculum.source,
                            'imported_resource_type': resource_payload.get('resource_type'),
                            'metadata': resource_payload.get('metadata') or {},
                            'extensions': resource_payload.get('extensions') or {},
                        },
                        created_by_user_id=auth.user_id,
                    )
                    db.add(resource)
                    await db.flush()
                    db.add(LessonResource(lesson_id=activated_lesson.id, resource_id=resource.id))
                    created_resources.append(resource)
                    resource_ids.append(resource.id)

                if payload.generate_assignments:
                    assignment = Assignment(
                        family_id=auth.family_id,
                        title=activated_lesson.name,
                        subject_id=subject.id,
                        description=activated_lesson.description,
                        status=AssignmentStatus.pending,
                        category=AssignmentCategory.homework,
                        attachments=_resource_attachments_for_import(created_resources),
                    )
                    db.add(assignment)
                    await db.flush()
                    assignment_ids.append(assignment.id)

    activated_at = datetime.now(UTC)
    curriculum.last_activated_at = activated_at
    curriculum.last_activation_summary = {
        'school_year_id': school_year.id,
        'package_ids': package_ids,
        'subject_ids': activated_subject_ids,
        'unit_ids': unit_ids,
        'lesson_ids': lesson_ids,
        'resource_ids': resource_ids,
        'assignment_ids': assignment_ids,
        'generated_assignments': payload.generate_assignments,
    }
    await db.commit()
    return CurriculumImportActivationRead(
        curriculum_id=curriculum.id,
        package_ids=package_ids,
        subject_ids=activated_subject_ids,
        unit_ids=unit_ids,
        lesson_ids=lesson_ids,
        resource_ids=resource_ids,
        assignment_ids=assignment_ids,
        generated_assignments=payload.generate_assignments,
        activated_at=activated_at,
    )


@router.delete('/curriculum/{curriculum_id:int}', status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_imported_curriculum(
    curriculum_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_capabilities(Capability.manage_curriculum, action='delete imported curriculum')),
) -> None:
    curriculum = await _get_imported_curriculum_or_404(db, curriculum_id, auth.family_id)
    await db.delete(curriculum)
    await db.commit()


@router.get('/curriculum/packages', response_model=list[CurriculumPackageDetail])
async def list_curriculum_packages(
    school_year_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_any_role(AppRole.teacher, AppRole.student, action='view curriculum packages')),
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
    auth: AuthSession = Depends(require_teacher(action='manage curriculum packages')),
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
    auth: AuthSession = Depends(require_any_role(AppRole.teacher, AppRole.student, action='view curriculum packages')),
) -> CurriculumPackage:
    return await _get_package_or_404(db, package_id, auth.family_id)


@router.put('/curriculum/packages/{package_id}', response_model=CurriculumPackageRead)
async def update_curriculum_package(
    package_id: int,
    payload: CurriculumPackageUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_teacher(action='manage curriculum packages')),
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
    auth: AuthSession = Depends(require_teacher(action='manage curriculum packages')),
) -> None:
    package = await _get_package_or_404(db, package_id, auth.family_id)
    await db.delete(package)
    await db.commit()


@router.post('/curriculum/packages/{package_id}/clone', response_model=CurriculumPackageDetail, status_code=status.HTTP_201_CREATED)
async def clone_curriculum_package(
    package_id: int,
    payload: CloneCurriculumPackageRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(require_teacher(action='clone curriculum packages')),
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
    auth: AuthSession = Depends(require_teacher(action='link resources to lessons')),
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
        require_teacher(action='unlink resources from lessons')
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
