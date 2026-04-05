from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App config
    ENVIRONMENT: str = "local"
    
    # Auth configuration
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200
    
    # DB & Broker
    DATABASE_URL: str
    REDIS_URL: str
    
    # AI APIs
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    
    # Integrations — Modal GPU Cloud
    MODAL_GPU_ENABLED: bool = False  # kill switch: set False to force mock fallback
    MODAL_TOKEN_ID: str | None = None
    MODAL_TOKEN_SECRET: str | None = None
    SMTP_HOST: str | None = None
    SMTP_PORT: int | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SLACK_WEBHOOK_URL: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
