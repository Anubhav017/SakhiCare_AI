from typing import Annotated

from pydantic import Field, HttpUrl, StringConstraints, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DB_CONNECTION: str
    AUTO_CREATE_TABLES: bool = False
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SESSION_COOKIE_SECURE: bool = True
    REMEMBER_ME_HOURS: int = Field(default=24, ge=1, le=168)
    OLLAMA_BASE_URL: HttpUrl = HttpUrl("http://127.0.0.1:11434")
    OLLAMA_TIMEOUT_SECONDS: float = Field(default=120, gt=0, allow_inf_nan=False)
    EMBEDDING_MODEL: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] = "nomic-embed-text"
    CHAT_MODEL: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = "llama3.2:3b"

    RAG_MAX_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)
    RAG_MAX_CHUNKS: int = Field(default=250, gt=0)
    RAG_CHUNK_SIZE: int = Field(default=1100, gt=0)
    RAG_CHUNK_OVERLAP: int = Field(default=180, ge=0)
    RAG_EMBED_BATCH_SIZE: int = Field(default=64, gt=0)
    RAG_PDF_TOP_K: int = Field(default=5, gt=0)
    RAG_PDF_MAX_DISTANCE: float = Field(default=0.55, ge=0, le=2)
    RAG_TASK_LIMIT: int = Field(default=200, gt=0)

    RAG_WORKER_POLL_SECONDS: float = Field(default=2, gt=0, allow_inf_nan=False)
    RAG_WORKER_LEASE_SECONDS: int = Field(default=300, gt=0)
    RAG_WORKER_MAX_ATTEMPTS: int = Field(default=3, gt=0)
    RAG_WORKER_RETRY_SECONDS: int = Field(default=15, gt=0)

    @model_validator(mode="after")
    def validate_rag_settings(self) -> "Settings":
        if self.RAG_CHUNK_OVERLAP >= self.RAG_CHUNK_SIZE:
            raise ValueError("RAG_CHUNK_OVERLAP must be less than RAG_CHUNK_SIZE")
        if self.RAG_WORKER_LEASE_SECONDS <= self.OLLAMA_TIMEOUT_SECONDS:
            raise ValueError("RAG_WORKER_LEASE_SECONDS must exceed OLLAMA_TIMEOUT_SECONDS")
        return self


settings = Settings()
