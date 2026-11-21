import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, func, update
from sqlalchemy.exc import SQLAlchemyError

from src.documents.ingestion import build_index
from src.documents.models import RagChunk, RagDocument
from src.utils.db import Session
from src.utils.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IndexJob:
    document_id: int
    token: str
    attempt: int
    content: bytes | None


class LeaseLost(Exception):
    pass


def _next_job() -> IndexJob | None:
    with Session.begin() as db:
        document = (
            db.query(RagDocument)
            .filter(
                RagDocument.status.in_(("pending", "processing")),
                RagDocument.available_at <= func.now(),
            )
            .order_by(RagDocument.available_at, RagDocument.id)
            .with_for_update(skip_locked=True)
            .first()
        )
        if document is None:
            return None
        if document.attempts >= settings.RAG_WORKER_MAX_ATTEMPTS:
            document.status = "failed"
            document.lease_token = None
            document.indexing_error = "Indexing did not finish before its final lease expired"
            return None
        token = uuid4().hex
        document.status = "processing"
        document.lease_token = token
        document.attempts += 1
        document.available_at = func.now() + timedelta(seconds=settings.RAG_WORKER_LEASE_SECONDS)
        return IndexJob(document.id, token, document.attempts, document.pdf_data)


def _apply_job_update(db, job: IndexJob, **values) -> None:
    result = db.execute(
        update(RagDocument)
        .where(
            RagDocument.id == job.document_id,
            RagDocument.status == "processing",
            RagDocument.lease_token == job.token,
            RagDocument.available_at > func.now(),
        )
        .values(**values)
    )
    if result.rowcount != 1:
        raise LeaseLost


def _renew(job: IndexJob) -> None:
    with Session.begin() as db:
        _apply_job_update(
            db, job, available_at=func.now() + timedelta(seconds=settings.RAG_WORKER_LEASE_SECONDS),
        )


def _finish(job: IndexJob, chunks: list[tuple[int, str, list[float]]]) -> None:
    with Session.begin() as db:
        _apply_job_update(
            db, job, status="ready", embedding_model=settings.embedding_identity,
            lease_token=None, indexing_error=None,
        )
        db.execute(delete(RagChunk).where(RagChunk.document_id == job.document_id))
        db.add_all(
            RagChunk(document_id=job.document_id, page=page, content=content, embedding=vector)
            for page, content, vector in chunks
        )


def _record_failure(job: IndexJob, exc: Exception) -> None:
    permanent = isinstance(exc, HTTPException) and 400 <= exc.status_code < 500
    retry = not permanent and job.attempt < settings.RAG_WORKER_MAX_ATTEMPTS
    detail = str(exc.detail) if isinstance(exc, HTTPException) else "Document indexing failed"
    with Session.begin() as db:
        _apply_job_update(
            db, job, status="pending" if retry else "failed", lease_token=None,
            indexing_error=None if retry else detail,
            available_at=func.now() + timedelta(seconds=settings.RAG_WORKER_RETRY_SECONDS),
        )
    logger.warning(
        "Indexing %s for document %s on attempt %s (%s)",
        "will retry" if retry else "failed", job.document_id, job.attempt, type(exc).__name__,
    )


def run_once() -> bool:
    job = _next_job()
    if job is None:
        return False
    try:
        try:
            if job.content is None:
                raise HTTPException(422, "Original PDF missing. Upload the PDF again to index it.")
            _finish(job, build_index(job.content, lambda: _renew(job)))
        except LeaseLost:
            raise
        except Exception as exc:
            _record_failure(job, exc)
    except LeaseLost:
        logger.info("Indexing lease lost for document %s", job.document_id)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Document indexing worker started")
    try:
        while True:
            try:
                if run_once():
                    continue
            except SQLAlchemyError as exc:
                logger.error("Document worker database operation failed (%s)", type(exc).__name__)
            time.sleep(settings.RAG_WORKER_POLL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Document indexing worker stopped")


if __name__ == "__main__":
    main()
