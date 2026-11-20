import json
import logging
import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException

from src.utils.settings import settings

logger = logging.getLogger(__name__)


def _request(endpoint: str, payload: dict) -> dict:
    request = Request(
        f"{str(settings.OLLAMA_BASE_URL).rstrip('/')}/api/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.OLLAMA_TIMEOUT_SECONDS) as response:
            result = json.load(response)
    except HTTPError as exc:
        logger.warning("Ollama %s returned HTTP %s", endpoint, exc.code)
        if exc.code == 404:
            raise HTTPException(503, f"Ollama could not find model {payload['model']}") from exc
        raise HTTPException(502, "Ollama rejected the request") from exc
    except (URLError, TimeoutError) as exc:
        logger.warning("Ollama %s was unavailable (%s)", endpoint, type(exc).__name__)
        raise HTTPException(503, "Could not reach Ollama") from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(502, "Could not read the Ollama response") from exc
    if not isinstance(result, dict):
        raise HTTPException(502, "Unexpected Ollama response")
    return result


def embed(texts: list[str]) -> list[list[float]]:
    result = _request("embed", {"model": settings.EMBEDDING_MODEL, "input": texts})
    vectors = result.get("embeddings")
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
        raise HTTPException(502, "Ollama returned invalid embeddings")
    return vectors


def chat(messages: list[dict[str, str]]) -> str:
    result = _request("chat", {
        "model": settings.CHAT_MODEL,
        "stream": False,
        "options": {"temperature": 0},
        "messages": messages,
    })
    message = result.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise HTTPException(502, "Ollama returned an invalid chat response")
    return message["content"] or "No answer generated"
