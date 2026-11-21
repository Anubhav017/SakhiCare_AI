from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.User.models import UserModel
from src.documents.models import RagChunk, RagDocument
from src.utils.ai_client import embed
from src.tasks.models import TaskModel
from src.utils.config import settings


def pdf_context(
    db: Session, user_id: int, question: str, document_id: int | None,
    *, guidelines_only: bool = False, language: str | None = None,
):
    document_scope = [
        RagDocument.user_id == user_id,
        RagDocument.status == "ready",
    ]
    if guidelines_only:
        document_scope.append(
            RagDocument.user_id.in_(select(UserModel.id).where(UserModel.role == "super_admin"))
        )
    if document_id is not None:
        document_scope.append(RagDocument.id == document_id)

    ready_documents = db.query(RagDocument.id).filter(*document_scope)
    active_model = RagDocument.embedding_model == settings.embedding_identity
    if guidelines_only and ready_documents.filter(active_model).first() is None:
        if ready_documents.first() is not None:
            raise HTTPException(409, {
                "code": "reindex_required",
                "message": "Ask is waiting for guidelines to be reindexed with the configured embedding model. Contact your Super Admin.",
            })
        return "", []

    vector = embed([question])[0]
    matching_dimensions = func.vector_dims(RagChunk.embedding) == len(vector)
    # Guard the distance operation even if PostgreSQL reorders the WHERE clauses.
    distance = case((matching_dimensions, RagChunk.embedding.cosine_distance(vector)))
    query = (
        db.query(
            RagChunk.id,
            RagChunk.page,
            RagChunk.content,
            RagDocument.id,
            RagDocument.filename,
            RagDocument.guideline_title,
            RagDocument.guideline_version,
            RagDocument.guideline_language,
            distance.label("distance"),
        )
        .select_from(RagChunk)
        .join(RagDocument, RagChunk.document_id == RagDocument.id)
        .filter(
            *document_scope,
            active_model,
            matching_dimensions,
        )
    )

    excerpts = []
    references = []
    query = query.filter(distance <= settings.RAG_PDF_MAX_DISTANCE).order_by(distance, RagChunk.id)
    matches = []
    if guidelines_only and language is not None:
        matches = query.filter(RagDocument.guideline_language == language).limit(settings.RAG_PDF_TOP_K).all()
    if not matches:
        matches = query.limit(settings.RAG_PDF_TOP_K).all()
    for chunk_id, page, content, matched_doc_id, filename, title, version, source_language, _ in matches:
        title = title or filename
        label = f"{title}, version {version}" if guidelines_only and version else title if guidelines_only else filename
        excerpts.append(f"[PDF chunk {chunk_id}; {label}; page {page}] {content}")
        reference = {
            "type": "pdf",
            "document_id": matched_doc_id,
            "filename": filename,
            "page": page,
            "chunk_id": chunk_id,
        }
        if guidelines_only:
            reference.update(title=title, version=version, language=source_language)
        references.append(reference)
    return "\n".join(excerpts), references


def task_context(db: Session, user_id: int):
    tasks = (
        db.query(TaskModel)
        .filter(TaskModel.user_id == user_id)
        .order_by(TaskModel.id)
        .limit(settings.RAG_TASK_LIMIT)
        .all()
    )
    excerpts = [
        f"[Task {task.id}] title={task.title!r}; "
        f"description={task.description!r}; completed={bool(task.is_completed)}"
        for task in tasks
    ]
    references = [{"type": "task", "task_id": task.id} for task in tasks]
    return "\n".join(excerpts), references
