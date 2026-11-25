import logging
import math
from functools import lru_cache

import httpx
from fastapi import HTTPException
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src.utils.config import AI_PROVIDERS, settings


logger = logging.getLogger(__name__)


@lru_cache
def _embedding_client() -> Embeddings:
    factory = AI_PROVIDERS[settings.EMBEDDING_PROVIDER].embeddings
    assert factory is not None
    return factory(settings)


@lru_cache
def _chat_model() -> BaseChatModel:
    factory = AI_PROVIDERS[settings.CHAT_PROVIDER].chat
    assert factory is not None
    return factory(settings)


@lru_cache
def _chat_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system}"),
        ("human", "{user}"),
    ])
    return prompt | _chat_model() | StrOutputParser()


def _invoke(operation, argument, provider: str, model: str):
    adapter = AI_PROVIDERS[provider]
    try:
        return operation(argument)
    except adapter.status_errors as exc:
        logger.warning("%s returned HTTP %s", provider, exc.status_code)
        if exc.status_code == 404:
            raise HTTPException(503, {
                "code": "model_unavailable",
                "message": f"The configured {provider} model {model} is unavailable. Check the model name and provider access.",
            }) from exc
        if exc.status_code in (429, 503):
            raise HTTPException(503, "AI provider is temporarily unavailable") from exc
        raise HTTPException(502, "AI provider rejected the request") from exc
    except (httpx.RequestError, ConnectionError, *adapter.connection_errors) as exc:
        logger.warning("%s was unavailable (%s)", provider, type(exc).__name__)
        raise HTTPException(503, "Could not reach the AI provider") from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(502, "Could not read the AI provider response") from exc


def _require_model_key() -> None:
    if not settings.MODEL_API_KEY or not settings.MODEL_API_KEY.get_secret_value().strip():
        raise HTTPException(503, "AI is not configured. Add MODEL_API_KEY to backend/.env.")


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    _require_model_key()
    vectors = _invoke(_embedding_client().embed_documents, texts, settings.EMBEDDING_PROVIDER, settings.EMBEDDING_MODEL)
    if (
        not isinstance(vectors, list)
        or len(vectors) != len(texts)
        or any(not isinstance(vector, list) or not vector for vector in vectors)
        or any(
            type(value) not in (int, float) or not math.isfinite(value)
            for vector in vectors
            for value in vector
        )
        or len({len(vector) for vector in vectors}) != 1
    ):
        raise HTTPException(502, "AI provider returned invalid embeddings")
    return vectors


def chat(*, system: str, user: str) -> str:
    _require_model_key()
    response = _invoke(_chat_chain().invoke, {"system": system, "user": user}, settings.CHAT_PROVIDER, settings.CHAT_MODEL)
    return response.strip() or "No answer generated"


def call_tool(*, tool: BaseTool, system: str, user: str) -> dict | None:
    """Ask the configured model for one allow-listed structured tool call."""
    _require_model_key()
    tool_model = _chat_model().bind_tools([tool], tool_choice=tool.name)
    response = _invoke(
        tool_model.invoke,
        [SystemMessage(content=system), HumanMessage(content=user)],
        settings.CHAT_PROVIDER,
        settings.CHAT_MODEL,
    )
    for call in getattr(response, "tool_calls", []):
        if call.get("name") == tool.name and isinstance(call.get("args"), dict):
            return call["args"]
    return None
