from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Annotated

from pydantic import AliasChoices, Field, SecretStr, HttpUrl, StringConstraints, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ollama import ResponseError
from openai import APIConnectionError, APIStatusError


@dataclass(frozen=True)
class AIProvider:
    chat: Callable[[Settings], BaseChatModel] | None = None
    embeddings: Callable[[Settings], Embeddings] | None = None
    requires_key: bool = False
    legacy_embedding_identity: bool = False
    status_errors: tuple[type[Exception], ...] = ()
    connection_errors: tuple[type[Exception], ...] = ()


def _ollama_options(settings: Settings) -> dict:
    return {
        "base_url": str(settings.OLLAMA_BASE_URL).rstrip("/"),
        "client_kwargs": {"timeout": settings.AI_TIMEOUT_SECONDS},
    }


def _hosted_options(settings: Settings) -> dict:
    return {
        "api_key": settings.MODEL_API_KEY,
        "timeout": settings.AI_TIMEOUT_SECONDS,
        "max_retries": 0,
    }


AI_PROVIDERS = {
    "ollama": AIProvider(
        chat=lambda cfg: ChatOllama(model=cfg.CHAT_MODEL, temperature=0, **_ollama_options(cfg)),
        embeddings=lambda cfg: OllamaEmbeddings(model=cfg.EMBEDDING_MODEL, **_ollama_options(cfg)),
        legacy_embedding_identity=True,
        status_errors=(ResponseError,),
    ),
    "openai": AIProvider(
        chat=lambda cfg: ChatOpenAI(model=cfg.CHAT_MODEL, **_hosted_options(cfg)),
        embeddings=lambda cfg: OpenAIEmbeddings(model=cfg.EMBEDDING_MODEL, **_hosted_options(cfg)),
        requires_key=True,
        status_errors=(APIStatusError,),
        connection_errors=(APIConnectionError,),
    ),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    DB_CONNECTION: str
    AUTO_CREATE_TABLES: bool = False
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SESSION_COOKIE_SECURE: bool = True
    REMEMBER_ME_HOURS: int = Field(default=24, ge=1, le=168)
    CHAT_PROVIDER: str
    EMBEDDING_PROVIDER: str
    MODEL_API_KEY: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_API_KEY", "OPENAI_API_KEY"),
    )
    OLLAMA_BASE_URL: HttpUrl = HttpUrl("http://127.0.0.1:11434")
    AI_TIMEOUT_SECONDS: float = Field(
        default=120, gt=0, allow_inf_nan=False,
        validation_alias=AliasChoices("AI_TIMEOUT_SECONDS", "OLLAMA_TIMEOUT_SECONDS"),
    )
    EMBEDDING_MODEL: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    CHAT_MODEL: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

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

    @property
    def embedding_identity(self) -> str:
        # Ollama documents created before provider selection use the bare model name.
        if AI_PROVIDERS[self.EMBEDDING_PROVIDER].legacy_embedding_identity:
            return self.EMBEDDING_MODEL
        return f"{self.EMBEDDING_PROVIDER}:{self.EMBEDDING_MODEL}"

    @model_validator(mode="after")
    def validate_rag_settings(self) -> "Settings":
        chat = AI_PROVIDERS.get(self.CHAT_PROVIDER)
        embeddings = AI_PROVIDERS.get(self.EMBEDDING_PROVIDER)
        if chat is None or chat.chat is None:
            raise ValueError(f"Unsupported chat provider: {self.CHAT_PROVIDER}")
        if embeddings is None or embeddings.embeddings is None:
            raise ValueError(f"Unsupported embedding provider: {self.EMBEDDING_PROVIDER}")
        if chat.requires_key or embeddings.requires_key:
            if not self.MODEL_API_KEY or not self.MODEL_API_KEY.get_secret_value().strip():
                raise ValueError("MODEL_API_KEY is required for the selected AI provider")
        reserved_prefixes = tuple(
            f"{name}:" for name, provider in AI_PROVIDERS.items()
            if provider.embeddings is not None and not provider.legacy_embedding_identity
        )
        if embeddings.legacy_embedding_identity and self.EMBEDDING_MODEL.startswith(reserved_prefixes):
            raise ValueError("Embedding model uses a reserved provider prefix")
        if len(self.embedding_identity) > 255:
            raise ValueError("Embedding provider and model identifier is too long")
        if self.RAG_CHUNK_OVERLAP >= self.RAG_CHUNK_SIZE:
            raise ValueError("RAG_CHUNK_OVERLAP must be less than RAG_CHUNK_SIZE")
        if self.RAG_WORKER_LEASE_SECONDS <= self.AI_TIMEOUT_SECONDS:
            raise ValueError("RAG_WORKER_LEASE_SECONDS must exceed AI_TIMEOUT_SECONDS")
        return self


settings = Settings()
