from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models import AuditAction, Family, FamilyMembership, FamilyRole, FamilySettings, User, UserPreference
from backend.schemas.auth import (
    BootstrapStatusResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    SessionResponse,
)
from backend.security import (
    AuthSession,
    bootstrap_required,
    clear_session_cookies,
    get_lockout_deadline,
    get_auth_session,
    get_login_membership,
    hash_password,
    resolve_external_app_roles,
    set_session_cookies,
    verify_password,
)
from backend.services.auth_oidc import OIDCConfigurationError, begin_oidc_login, complete_oidc_login
from backend.services.auth_provisioning import ExternalIdentity, provision_external_identity
from backend.services.auth_saml import SAMLConfigurationError, begin_saml_login, complete_saml_login, get_metadata_xml
from backend.services.audit import log_event
from backend.services.gradebook import ensure_default_grade_scale
from backend.services.maintenance import get_maintenance_status, membership_can_bypass_maintenance
from backend.services.notifications import create_security_alert_for_user
from backend.services.preferences import DEFAULT_USER_PREFERENCES, serialize_user_preferences

router = APIRouter(prefix='/auth', tags=['auth'])


def _set_session_cookie(
    response: Response,
    request: Request | None,
    *,
    user_id: int,
    family_id: int,
    app_roles: list[str] | None = None,
) -> None:
    set_session_cookies(response, request, user_id=user_id, family_id=family_id, app_roles=app_roles)


def _auth_session_from_record(
    user: User,
    membership: FamilyMembership,
    family: Family,
    preferences: UserPreference | None = None,
) -> AuthSession:
    family_settings = family.__dict__.get('family_settings')
    return AuthSession(
        user_id=user.id,
        family_id=family.id,
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider,
        role=membership.role.value,
        is_owner=membership.is_owner,
        family_name=family.name,
        family_state_code=family_settings.state_code if family_settings else 'CUSTOM',
        enabled_features=family_settings.enabled_features if family_settings else {},
        student_id=membership.student_id,
        ui_preferences=serialize_user_preferences(preferences),
    )


def _is_locked(user: User) -> bool:
    if user.locked_until is None:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > datetime.now(timezone.utc)


async def _find_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _register_failed_login(db: AsyncSession, user: User) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.auth_lockout_threshold:
        user.locked_until = get_lockout_deadline()
        user.failed_login_attempts = 0
        await create_security_alert_for_user(
            db,
            user_id=user.id,
            title='Account locked after repeated sign-in failures',
            message='We temporarily locked this account after repeated unsuccessful sign-in attempts. Confirm the password and review recent access activity.',
        )
    await db.commit()


async def _reset_failed_login(db: AsyncSession, user: User) -> None:
    if user.failed_login_attempts == 0 and user.locked_until is None:
        return
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()


def _session_response(auth: AuthSession, message: str | None = None) -> SessionResponse:
    return SessionResponse(
        authenticated=True,
        user={
            'id': auth.user_id,
            'email': auth.email,
            'display_name': auth.display_name,
            'is_active': True,
            'auth_provider': auth.auth_provider,
        },
        family={
            'id': auth.family_id,
            'name': auth.family_name,
            'state_code': auth.family_state_code,
            'enabled_features': auth.enabled_features or {},
        },
        membership={'role': auth.role, 'is_owner': auth.is_owner, 'student_id': auth.student_id},
        ui_preferences=auth.ui_preferences or DEFAULT_USER_PREFERENCES.model_dump(),
        message=message,
    )


def _redirect_to_login_error(message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/login?error={quote(message)}", status_code=status.HTTP_302_FOUND)


def _redirect_to_app() -> RedirectResponse:
    return RedirectResponse(url='/', status_code=status.HTTP_302_FOUND)


@router.get('/bootstrap', response_model=BootstrapStatusResponse)
async def bootstrap_status(db: AsyncSession = Depends(get_db)) -> BootstrapStatusResponse:
    return BootstrapStatusResponse(bootstrap_required=await bootstrap_required(db))


@router.post('/register', response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    maintenance = await get_maintenance_status(db)
    if maintenance.active:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=maintenance.message)
    if not await bootstrap_required(db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Bootstrap is no longer available')

    family = Family(
        name=payload.family_name.strip(),
        settings={'timezone': payload.timezone, 'grading_scale': payload.grading_scale},
    )
    user = User(
        email=payload.email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    membership = FamilyMembership(role=FamilyRole.parent, is_owner=True, invited_at=now, accepted_at=now)
    membership.user = user
    membership.family = family
    family_settings = FamilySettings(family=family, timezone=payload.timezone.strip(), grading_scale=payload.grading_scale.strip())
    user_preferences = UserPreference(user=user, **DEFAULT_USER_PREFERENCES.model_dump())

    db.add_all([family, user, membership, family_settings, user_preferences])
    await db.flush()
    await ensure_default_grade_scale(db, family.id)
    await db.commit()

    auth = AuthSession(
        user_id=user.id,
        family_id=family.id,
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider,
        role=membership.role.value,
        is_owner=membership.is_owner,
        family_name=family.name,
        family_state_code=family_settings.state_code,
        enabled_features=family_settings.enabled_features,
        student_id=membership.student_id,
        ui_preferences=serialize_user_preferences(user_preferences),
    )
    _set_session_cookie(response, request, user_id=user.id, family_id=family.id)
    return _session_response(auth, message='Owner account created')


@router.post('/login', response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    maintenance = await get_maintenance_status(db)
    membership_row = await get_login_membership(db, email=payload.email, family_id=payload.family_id)
    if maintenance.active and (membership_row is None or not membership_can_bypass_maintenance(membership_row[1])):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=maintenance.message)
    if membership_row is None:
        user = await _find_user_by_email(db, payload.email)
        if user is not None:
            if _is_locked(user):
                raise HTTPException(status_code=status.HTTP_423_LOCKED, detail='Account temporarily locked. Try again later.')
            await _register_failed_login(db, user)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')

    user, membership, family, state_code, enabled_features, preferences = membership_row
    if _is_locked(user):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail='Account temporarily locked. Try again later.')
    if not verify_password(payload.password, user.password_hash):
        await _register_failed_login(db, user)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')

    await _reset_failed_login(db, user)
    _set_session_cookie(response, request, user_id=user.id, family_id=family.id)
    auth = AuthSession(
        user_id=user.id,
        family_id=family.id,
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider,
        role=membership.role.value,
        is_owner=membership.is_owner,
        family_name=family.name,
        family_state_code=(state_code or 'CUSTOM').upper(),
        enabled_features=enabled_features or {},
        student_id=membership.student_id,
        ui_preferences=serialize_user_preferences(preferences),
    )
    await log_event(
        db,
        action=AuditAction.login,
        actor=user,
        family_id=family.id,
        target_type='session',
        target_id=f'{family.id}:{user.id}',
        before={'authenticated': False},
        after={
            'authenticated': True,
            'family_id': family.id,
            'user_id': user.id,
            'role': membership.role.value,
            'auth_provider': user.auth_provider,
        },
        request=request,
    )
    await db.commit()
    return _session_response(auth, message='Login successful')


@router.post('/logout')
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthSession = Depends(get_auth_session),
) -> dict[str, str]:
    await log_event(
        db,
        action=AuditAction.logout,
        actor=auth,
        family_id=auth.family_id,
        target_type='session',
        target_id=f'{auth.family_id}:{auth.user_id}',
        before={
            'authenticated': True,
            'family_id': auth.family_id,
            'user_id': auth.user_id,
            'role': auth.role,
            'auth_provider': auth.auth_provider,
        },
        after={'authenticated': False},
        request=request,
    )
    await db.commit()
    clear_session_cookies(response, request)
    return {'status': 'logged_out'}


@router.get('/me', response_model=SessionResponse)
async def me(_: Request, auth: AuthSession = Depends(get_auth_session)) -> SessionResponse:
    return _session_response(auth)


async def _complete_external_login(
    *,
    identity: ExternalIdentity,
    request: Request,
    db: AsyncSession,
) -> RedirectResponse:
    provisioned = await provision_external_identity(db, identity)
    maintenance = await get_maintenance_status(db)
    if maintenance.active and not membership_can_bypass_maintenance(provisioned.membership):
        return _redirect_to_login_error(maintenance.message)
    app_roles: list[str] | None = None
    if identity.roles:
        app_roles = resolve_external_app_roles(list(identity.roles))
        if not app_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='No configured application role mapping matched the external identity roles.',
            )
    response = _redirect_to_app()
    _set_session_cookie(
        response,
        request,
        user_id=provisioned.user.id,
        family_id=provisioned.family.id,
        app_roles=app_roles,
    )
    return response


@router.get('/oidc/login')
async def oidc_login(request: Request):
    try:
        return await begin_oidc_login(request)
    except OIDCConfigurationError as exc:
        return _redirect_to_login_error(str(exc))


@router.get('/oidc/callback')
async def oidc_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        identity = await complete_oidc_login(request)
        return await _complete_external_login(identity=identity, request=request, db=db)
    except HTTPException as exc:
        return _redirect_to_login_error(exc.detail)
    except OIDCConfigurationError as exc:
        return _redirect_to_login_error(str(exc))


@router.get('/saml/metadata')
async def saml_metadata() -> Response:
    try:
        return Response(content=get_metadata_xml(), media_type='application/xml')
    except SAMLConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/saml/login')
async def saml_login(request: Request):
    try:
        return RedirectResponse(url=await begin_saml_login(request), status_code=status.HTTP_302_FOUND)
    except SAMLConfigurationError as exc:
        return _redirect_to_login_error(str(exc))


@router.post('/saml/acs')
async def saml_acs(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        identity = await complete_saml_login(request)
        return await _complete_external_login(identity=identity, request=request, db=db)
    except HTTPException as exc:
        return _redirect_to_login_error(exc.detail)
    except SAMLConfigurationError as exc:
        return _redirect_to_login_error(str(exc))
