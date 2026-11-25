from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = Path("storage/uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 1024 * 64  # 64 KB
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        extra="ignore"
    )


settings = Settings()
