import json

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Homeschool Hero API'
    api_prefix: str = '/api'

    database_url: str = Field('sqlite+aiosqlite:///./homeschool.db', alias='DATABASE_URL')

    postgres_user: str = Field('homeschool', alias='POSTGRES_USER')
    postgres_password: str = Field('changeme', alias='POSTGRES_PASSWORD')
    postgres_db: str = Field('homeschool_hero', alias='POSTGRES_DB')

    secret_key: str = Field('dev-secret-change-me', alias='SECRET_KEY')
    session_cookie_name: str = Field('homeschool_session', alias='SESSION_COOKIE_NAME')
    csrf_cookie_name: str = Field('homeschool_csrf', alias='CSRF_COOKIE_NAME')
    session_max_age_seconds: int = Field(28800, alias='SESSION_MAX_AGE_SECONDS')
    session_cookie_secure: bool = Field(False, alias='SESSION_COOKIE_SECURE')
    session_rotation_seconds: int = Field(1800, alias='SESSION_ROTATION_SECONDS')
    tls_enabled: bool = Field(False, alias='TLS_ENABLED')
    https_redirect_enabled: bool = Field(False, alias='HTTPS_REDIRECT_ENABLED')
    hsts_enabled: bool = Field(True, alias='HSTS_ENABLED')
    hsts_max_age_seconds: int = Field(31536000, alias='HSTS_MAX_AGE_SECONDS')
    hsts_include_subdomains: bool = Field(True, alias='HSTS_INCLUDE_SUBDOMAINS')
    hsts_preload: bool = Field(False, alias='HSTS_PRELOAD')
    password_min_length: int = Field(12, alias='PASSWORD_MIN_LENGTH')
    auth_lockout_threshold: int = Field(5, alias='AUTH_LOCKOUT_THRESHOLD')
    auth_lockout_minutes: int = Field(15, alias='AUTH_LOCKOUT_MINUTES')
    auth_provider: str = Field('local', alias='AUTH_PROVIDER')
    oidc_client_id: str | None = Field(default=None, alias='OIDC_CLIENT_ID')
    oidc_client_secret: str | None = Field(default=None, alias='OIDC_CLIENT_SECRET')
    oidc_discovery_url: str | None = Field(default=None, alias='OIDC_DISCOVERY_URL')
    oidc_roles_claim: str = Field('roles', alias='OIDC_ROLES_CLAIM')
    oidc_groups_claim: str = Field('groups', alias='OIDC_GROUPS_CLAIM')
    oidc_group_role_map: str = Field('', alias='OIDC_GROUP_ROLE_MAP')
    saml_metadata_url: str | None = Field(default=None, alias='SAML_METADATA_URL')
    saml_entity_id: str | None = Field(default=None, alias='SAML_ENTITY_ID')
    saml_acs_url: str | None = Field(default=None, alias='SAML_ACS_URL')
    saml_role_attribute: str = Field(
        'http://schemas.microsoft.com/ws/2008/06/identity/claims/role',
        alias='SAML_ROLE_ATTRIBUTE',
    )
    auth_auto_provision_mode: str = Field('default_family', alias='AUTH_AUTO_PROVISION_MODE')
    auth_default_family_name: str = Field('SSO Users', alias='AUTH_DEFAULT_FAMILY_NAME')
    role_mapping_admin_raw: str = Field('Admin', alias='ROLE_MAPPING_ADMIN')
    role_mapping_teacher_raw: str = Field('Teacher', alias='ROLE_MAPPING_TEACHER')
    role_mapping_student_raw: str = Field('Student', alias='ROLE_MAPPING_STUDENT')
    jwt_enabled: bool = Field(False, alias='JWT_ENABLED')
    jwt_jwks_url: str = Field('', alias='JWT_JWKS_URL')
    jwt_issuer: str = Field('', alias='JWT_ISSUER')
    jwt_audience: str = Field('', alias='JWT_AUDIENCE')
    jwt_tenant_id: str = Field('', alias='JWT_TENANT_ID')
    jwt_secret: str = Field('', alias='JWT_SECRET')
    jwt_algorithm: str = Field('RS256', alias='JWT_ALGORITHM')

    bootstrap_owner_email: str = Field('owner@homeschool-hero.local', alias='BOOTSTRAP_OWNER_EMAIL')
    bootstrap_owner_display_name: str = Field('Family Owner', alias='BOOTSTRAP_OWNER_DISPLAY_NAME')
    bootstrap_family_name: str = Field('My Family', alias='BOOTSTRAP_FAMILY_NAME')
    bootstrap_timezone: str = Field('UTC', alias='BOOTSTRAP_TIMEZONE')
    bootstrap_grading_scale: str = Field('letter', alias='BOOTSTRAP_GRADING_SCALE')

    legacy_family_password: str = Field('changeme', alias='FAMILY_PASSWORD')
    legacy_family_password_hash: str | None = Field(default=None, alias='FAMILY_PASSWORD_HASH')

    ai_provider: str = Field('ollama', alias='AI_PROVIDER')
    ollama_host: str = Field('http://ollama:11434', alias='OLLAMA_HOST')
    ollama_model: str = Field('llama3.2', alias='OLLAMA_MODEL')
    openai_api_key: str | None = Field(default=None, alias='OPENAI_API_KEY')
    grading_request_timeout_seconds: float = Field(120.0, alias='GRADING_REQUEST_TIMEOUT_SECONDS')
    ocr_request_timeout_seconds: float = Field(120.0, alias='OCR_REQUEST_TIMEOUT_SECONDS')
    grading_retry_attempts: int = Field(3, alias='GRADING_RETRY_ATTEMPTS')
    grading_retry_backoff_seconds: float = Field(1.0, alias='GRADING_RETRY_BACKOFF_SECONDS')
    ai_circuit_breaker_threshold: int = Field(3, alias='AI_CIRCUIT_BREAKER_THRESHOLD')
    ai_circuit_breaker_reset_seconds: float = Field(300.0, alias='AI_CIRCUIT_BREAKER_RESET_SECONDS')

    confidence_threshold: float = Field(0.8, alias='CONFIDENCE_THRESHOLD')
    grading_poll_interval: float = Field(5.0, alias='GRADING_POLL_INTERVAL')
    upload_dir: str = Field('/data/uploads', alias='UPLOAD_DIR')
    upload_max_bytes: int = Field(25 * 1024 * 1024, alias='UPLOAD_MAX_BYTES')
    enable_metrics_endpoint: bool = Field(False, alias='ENABLE_METRICS_ENDPOINT')
    log_level: str = Field('INFO', alias='LOG_LEVEL')
    log_json: bool | None = Field(default=None, alias='LOG_JSON')
    upload_allowed_mime_types_raw: str = Field(
        'application/pdf,image/jpeg,image/png,image/heic,image/heif,image/tiff,image/webp',
        alias='UPLOAD_ALLOWED_MIME_TYPES',
    )

    invitation_expiry_days: int = Field(7, alias='INVITATION_EXPIRY_DAYS')
    invitation_base_url: str | None = Field(default=None, alias='INVITATION_BASE_URL')
    smtp_host: str | None = Field(default=None, alias='SMTP_HOST')
    smtp_port: int = Field(587, alias='SMTP_PORT')
    smtp_username: str | None = Field(default=None, alias='SMTP_USERNAME')
    smtp_password: str | None = Field(default=None, alias='SMTP_PASSWORD')
    smtp_from_email: str | None = Field(default=None, alias='SMTP_FROM_EMAIL')
    smtp_use_tls: bool = Field(True, alias='SMTP_USE_TLS')
    email_provider: str = Field('smtp', alias='EMAIL_PROVIDER')
    acs_connection_string: str | None = Field(default=None, alias='ACS_CONNECTION_STRING')
    acs_sender_address: str | None = Field(default=None, alias='ACS_SENDER_ADDRESS')
    backup_destination: str = Field('local', alias='BACKUP_DESTINATION')
    backup_target: str | None = Field(default=None, alias='BACKUP_TARGET')
    backup_schedule: str = Field('0 2 * * *', alias='BACKUP_SCHEDULE')
    backup_retention_days: int = Field(14, alias='BACKUP_RETENTION_DAYS')
    backup_retention_count: int = Field(3, alias='BACKUP_RETENTION_COUNT')
    backup_filename_prefix: str = Field('homeschool-hero', alias='BACKUP_FILENAME_PREFIX')
    backup_scheduler_enabled: bool = Field(True, alias='BACKUP_SCHEDULER_ENABLED')
    backup_smb_host: str | None = Field(default=None, alias='BACKUP_SMB_HOST')
    backup_smb_share: str | None = Field(default=None, alias='BACKUP_SMB_SHARE')
    backup_smb_user: str | None = Field(default=None, alias='BACKUP_SMB_USER')
    backup_smb_password: str | None = Field(default=None, alias='BACKUP_SMB_PASSWORD')
    backup_nfs_host: str | None = Field(default=None, alias='BACKUP_NFS_HOST')
    backup_nfs_path: str | None = Field(default=None, alias='BACKUP_NFS_PATH')
    backup_encryption_key: str | None = Field(default=None, alias='BACKUP_ENCRYPTION_KEY')
    maintenance_mode: bool = Field(False, alias='MAINTENANCE_MODE')
    maintenance_message: str = Field(
        'Homeschool Hero is temporarily unavailable while we perform maintenance. Please check back soon.',
        alias='MAINTENANCE_MESSAGE',
    )
    demo_mode: bool = Field(False, alias='DEMO_MODE')
    testing: bool = Field(False, alias='TESTING')

    @property
    def upload_allowed_mime_types(self) -> set[str]:
        return {item.strip().lower() for item in self.upload_allowed_mime_types_raw.split(',') if item.strip()}

    @property
    def external_role_mappings(self) -> dict[str, str]:
        mappings: dict[str, str] = {}
        for app_role, raw_value in (
            ('admin', self.role_mapping_admin_raw),
            ('teacher', self.role_mapping_teacher_raw),
            ('student', self.role_mapping_student_raw),
        ):
            for candidate in {item.strip().casefold() for item in raw_value.split(',') if item.strip()}:
                existing = mappings.get(candidate)
                if existing is not None and existing != app_role:
                    raise ValueError(f"External role '{candidate}' is mapped to both '{existing}' and '{app_role}'.")
                mappings[candidate] = app_role
        return mappings

    @property
    def oidc_group_role_mappings(self) -> dict[str, str]:
        raw_value = self.oidc_group_role_map.strip()
        if not raw_value:
            return {}
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            raise ValueError('OIDC_GROUP_ROLE_MAP must be a JSON object mapping groups to role names.')

        mappings: dict[str, str] = {}
        for raw_group, raw_role in parsed.items():
            if not isinstance(raw_group, str) or not raw_group.strip():
                raise ValueError('OIDC_GROUP_ROLE_MAP keys must be non-empty strings.')
            if not isinstance(raw_role, str) or not raw_role.strip():
                raise ValueError('OIDC_GROUP_ROLE_MAP values must be non-empty strings.')
            mappings[raw_group.strip()] = raw_role.strip()
        return mappings


settings = Settings()
