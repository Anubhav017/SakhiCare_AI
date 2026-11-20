import hashlib
from collections.abc import Callable
import io

from fastapi import HTTPException
from pypdf import PdfReader
from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.documents.models import RagChunk, RagDocument
from src.documents.schemas import DocumentUploadResponse

from src.utils.ai_client import embed
from src.utils.settings import settings


def _chunks(text: str):
    text = " ".join(text.split())
    size = settings.RAG_CHUNK_SIZE
    step = size - settings.RAG_CHUNK_OVERLAP
    for start in range(0, len(text), step):
        yield text[start:start + size]
        if start + size >= len(text):
            break


def _extract_chunks(content: bytes) -> list[tuple[int, str]]:
    pieces = []
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise HTTPException(400, "Encrypted PDFs are unsupported")
        for page_number, page in enumerate(reader.pages, 1):
            for chunk in _chunks(page.extract_text() or ""):
                if len(pieces) >= settings.RAG_MAX_CHUNKS:
                    raise HTTPException(
                        413, f"PDF has too many text chunks (limit {settings.RAG_MAX_CHUNKS})"
                    )
                pieces.append((page_number, chunk))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "Could not read PDF") from exc
    if not pieces:
        raise HTTPException(422, "No extractable text; scanned PDFs need OCR")
    return pieces


def build_index(content: bytes, renew_lease: Callable[[], None]):
    pieces = _extract_chunks(content)
    vectors = []
    batch_size = settings.RAG_EMBED_BATCH_SIZE
    for start in range(0, len(pieces), batch_size):
        renew_lease()
        batch = pieces[start:start + batch_size]
        vectors.extend(embed([text for _, text in batch]))
    if len({len(vector) for vector in vectors}) != 1:
        raise HTTPException(502, "Ollama returned embeddings of different dimensions")
    return [(page, text, vector) for (page, text), vector in zip(pieces, vectors, strict=True)]


def enqueue_pdf(db: Session, user_id: int, filename: str, content: bytes) -> DocumentUploadResponse:
    if len(content) > settings.RAG_MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"PDF limit is {settings.RAG_MAX_UPLOAD_BYTES} bytes")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(400, "Expected a PDF file")

    digest = hashlib.sha256(content).hexdigest()
    document_id = db.execute(
        insert(RagDocument)
        .values(user_id=user_id, filename=filename[:255], sha256=digest, pdf_data=content, status="pending")
        .on_conflict_do_nothing(constraint="uq_rag_user_hash")
        .returning(RagDocument.id)
    ).scalar_one_or_none()
    if document_id is not None:
        response = DocumentUploadResponse(
            document_id=document_id, status="pending", chunks=0, duplicate=False,
        )
    else:
        document = (
            db.query(RagDocument)
            .filter_by(user_id=user_id, sha256=digest)
            .with_for_update()
            .one()
        )
        duplicate = True
        if document.status == "failed" or (
            document.status == "ready" and document.embedding_model != settings.EMBEDDING_MODEL
        ):
            document.pdf_data = content
            document.status = "pending"
            document.attempts = 0
            document.available_at = func.now()
            document.lease_token = None
            document.indexing_error = None
            duplicate = False
        elif document.status == "ready":
            db.execute(
                update(RagDocument)
                .where(RagDocument.id == document.id, RagDocument.pdf_data.is_(None))
                .values(pdf_data=content)
            )

        count = 0
        if document.status == "ready":
            count = db.query(RagChunk.id).filter_by(document_id=document.id).count()
        response = DocumentUploadResponse(
            document_id=document.id, status=document.status, chunks=count, duplicate=duplicate,
        )
    db.commit()
    return response
