from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Homeschool Hero API"
    api_prefix: str = "/api"

    database_url: str = Field("sqlite+aiosqlite:///./homeschool.db", alias="DATABASE_URL")

    postgres_user: str = Field("homeschool", alias="POSTGRES_USER")
    postgres_password: str = Field("changeme", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field("homeschool_hero", alias="POSTGRES_DB")

    secret_key: str = Field("dev-secret-change-me", alias="SECRET_KEY")
    session_cookie_name: str = Field("homeschool_session", alias="SESSION_COOKIE_NAME")
    session_max_age_seconds: int = Field(28800, alias="SESSION_MAX_AGE_SECONDS")

    family_password: str = Field("changeme", alias="FAMILY_PASSWORD")
    family_password_hash: str | None = Field(default=None, alias="FAMILY_PASSWORD_HASH")
    family_pin: str = Field("1234", alias="FAMILY_PIN")
    family_pin_hash: str | None = Field(default=None, alias="FAMILY_PIN_HASH")

    ai_provider: str = Field("ollama", alias="AI_PROVIDER")
    ollama_host: str = Field("http://ollama:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field("llama3", alias="OLLAMA_MODEL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    confidence_threshold: float = Field(0.8, alias="CONFIDENCE_THRESHOLD")
    grading_poll_interval: float = Field(5.0, alias="GRADING_POLL_INTERVAL")
    upload_dir: str = Field("/data/uploads", alias="UPLOAD_DIR")
    testing: bool = Field(False, alias="TESTING")


settings = Settings()
