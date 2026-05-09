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
    session_max_age_seconds: int = Field(28800, alias='SESSION_MAX_AGE_SECONDS')
    session_cookie_secure: bool = Field(False, alias='SESSION_COOKIE_SECURE')

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

    confidence_threshold: float = Field(0.8, alias='CONFIDENCE_THRESHOLD')
    grading_poll_interval: float = Field(5.0, alias='GRADING_POLL_INTERVAL')
    upload_dir: str = Field('/data/uploads', alias='UPLOAD_DIR')

    invitation_expiry_days: int = Field(7, alias='INVITATION_EXPIRY_DAYS')
    invitation_base_url: str | None = Field(default=None, alias='INVITATION_BASE_URL')
    smtp_host: str | None = Field(default=None, alias='SMTP_HOST')
    smtp_port: int = Field(587, alias='SMTP_PORT')
    smtp_username: str | None = Field(default=None, alias='SMTP_USERNAME')
    smtp_password: str | None = Field(default=None, alias='SMTP_PASSWORD')
    smtp_from_email: str | None = Field(default=None, alias='SMTP_FROM_EMAIL')
    smtp_use_tls: bool = Field(True, alias='SMTP_USE_TLS')
    backup_target: str | None = Field(default=None, alias='BACKUP_TARGET')

    testing: bool = Field(False, alias='TESTING')


settings = Settings()
