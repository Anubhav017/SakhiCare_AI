import logging
import math
from functools import lru_cache

import httpx
from fastapi import HTTPException
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.embeddings import Embeddings

from src.utils.config import AI_PROVIDERS, settings


logger = logging.getLogger(__name__)


@lru_cache
def _embedding_client() -> Embeddings:
    factory = AI_PROVIDERS[settings.EMBEDDING_PROVIDER].embeddings
    assert factory is not None
    return factory(settings)


@lru_cache
def _chat_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system}"),
        ("human", "{user}"),
    ])
    factory = AI_PROVIDERS[settings.CHAT_PROVIDER].chat
    assert factory is not None
    return prompt | factory(settings) | StrOutputParser()


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


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
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
    response = _invoke(_chat_chain().invoke, {"system": system, "user": user}, settings.CHAT_PROVIDER, settings.CHAT_MODEL)
    return response.strip() or "No answer generated"
