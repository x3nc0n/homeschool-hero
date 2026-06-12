from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import get_db
from backend.models import AttendanceExcuse, PortfolioEntry, Resource, Submission
from backend.security import AuthSession, get_auth_session
from backend.services.authorization import Capability, ensure_student_scope, has_capability
from backend.services.storage import resolve_stored_upload_path

router = APIRouter(prefix='/files', tags=['files'])


@dataclass(slots=True)
class AuthorizedFile:
    absolute_path: Path
    media_type: str | None
    filename: str | None


def _stored_path_matches(stored_path: str | None, requested_relative_path: Path) -> bool:
    if not stored_path:
        return False
    try:
        actual_relative_path, _ = resolve_stored_upload_path(settings.upload_dir, stored_path)
    except ValueError:
        return False
    return actual_relative_path.as_posix() == requested_relative_path.as_posix()


def _forbidden(action: str, auth: AuthSession) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{auth.role}' is not allowed to {action}.")


async def _resolve_submission_file(
    db: AsyncSession,
    *,
    auth: AuthSession,
    requested_relative_path: Path,
    requested_absolute_path: Path,
) -> AuthorizedFile | None:
    parts = requested_relative_path.parts
    if len(parts) != 5 or not all(part.isdigit() for part in parts[:4]):
        return None

    family_id = int(parts[0])
    student_id = int(parts[1])
    assignment_id = int(parts[2])
    submission_id = int(parts[3])
    if family_id != auth.family_id:
        return None
    if not has_capability(auth, Capability.read_submissions):
        raise _forbidden('view submissions', auth)

    submission = (
        await db.execute(
            select(Submission).where(
                Submission.id == submission_id,
                Submission.family_id == family_id,
                Submission.student_id == student_id,
                Submission.assignment_id == assignment_id,
            )
        )
    ).scalar_one_or_none()
    if submission is None or not _stored_path_matches(submission.file_path, requested_relative_path):
        return None

    ensure_student_scope(auth, submission.student_id, action='view submissions')
    return AuthorizedFile(
        absolute_path=requested_absolute_path,
        media_type=submission.file_type or mimetypes.guess_type(submission.file_name)[0],
        filename=submission.original_filename or submission.file_name,
    )


async def _resolve_portfolio_attachment(
    db: AsyncSession,
    *,
    auth: AuthSession,
    requested_relative_path: Path,
    requested_absolute_path: Path,
) -> AuthorizedFile | None:
    parts = requested_relative_path.parts
    if len(parts) < 5 or parts[0] != 'portfolio' or not all(part.isdigit() for part in parts[1:4]):
        return None

    family_id = int(parts[1])
    student_id = int(parts[2])
    entry_id = int(parts[3])
    if family_id != auth.family_id:
        return None

    entry = (
        await db.execute(
            select(PortfolioEntry).where(
                PortfolioEntry.id == entry_id,
                PortfolioEntry.family_id == family_id,
                PortfolioEntry.student_id == student_id,
            )
        )
    ).scalar_one_or_none()
    if entry is None or not any(_stored_path_matches(item, requested_relative_path) for item in entry.attachments or []):
        return None

    ensure_student_scope(auth, entry.student_id, action='view portfolio entries')
    return AuthorizedFile(
        absolute_path=requested_absolute_path,
        media_type=mimetypes.guess_type(requested_absolute_path.name)[0],
        filename=requested_absolute_path.name,
    )


async def _resolve_resource_file(
    db: AsyncSession,
    *,
    auth: AuthSession,
    requested_relative_path: Path,
    requested_absolute_path: Path,
) -> AuthorizedFile | None:
    parts = requested_relative_path.parts
    if not parts or parts[0] != 'resources':
        return None
    if not has_capability(auth, Capability.read_curriculum):
        raise _forbidden('view curriculum resources', auth)

    resources = (
        await db.execute(select(Resource).where(Resource.family_id == auth.family_id, Resource.file_path.is_not(None)))
    ).scalars()
    for resource in resources:
        if _stored_path_matches(resource.file_path, requested_relative_path):
            return AuthorizedFile(
                absolute_path=requested_absolute_path,
                media_type=mimetypes.guess_type(requested_absolute_path.name)[0],
                filename=requested_absolute_path.name,
            )
    return None


async def _resolve_attendance_document(
    db: AsyncSession,
    *,
    auth: AuthSession,
    requested_relative_path: Path,
    requested_absolute_path: Path,
) -> AuthorizedFile | None:
    parts = requested_relative_path.parts
    if len(parts) != 1 or not parts[0].startswith('attendance-excuse-'):
        return None
    if not has_capability(auth, Capability.read_students):
        raise _forbidden('view attendance documents', auth)

    excuses = (
        await db.execute(
            select(AttendanceExcuse)
            .options(selectinload(AttendanceExcuse.attendance_record))
            .where(AttendanceExcuse.family_id == auth.family_id, AttendanceExcuse.document_path.is_not(None))
        )
    ).scalars()
    for excuse in excuses:
        if not _stored_path_matches(excuse.document_path, requested_relative_path):
            continue
        if excuse.attendance_record is None:
            return None
        ensure_student_scope(auth, excuse.attendance_record.student_id, action='view attendance records')
        return AuthorizedFile(
            absolute_path=requested_absolute_path,
            media_type=mimetypes.guess_type(requested_absolute_path.name)[0],
            filename=requested_absolute_path.name,
        )
    return None


async def _resolve_authorized_file(
    db: AsyncSession,
    *,
    auth: AuthSession,
    file_path: str,
) -> AuthorizedFile:
    try:
        requested_relative_path, requested_absolute_path = resolve_stored_upload_path(settings.upload_dir, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='File not found') from exc

    for resolver in (
        _resolve_submission_file,
        _resolve_portfolio_attachment,
        _resolve_resource_file,
        _resolve_attendance_document,
    ):
        authorized = await resolver(
            db,
            auth=auth,
            requested_relative_path=requested_relative_path,
            requested_absolute_path=requested_absolute_path,
        )
        if authorized is not None:
            if not authorized.absolute_path.exists() or not authorized.absolute_path.is_file():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='File not found')
            return authorized

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='File not found')


@router.get('/{file_path:path}')
async def serve_uploaded_file(
    file_path: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> FileResponse:
    authorized_file = await _resolve_authorized_file(db, auth=auth, file_path=file_path)
    return FileResponse(
        path=authorized_file.absolute_path,
        media_type=authorized_file.media_type,
        filename=authorized_file.filename,
    )
