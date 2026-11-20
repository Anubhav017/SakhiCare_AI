from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.User.models import UserModel
from src.documents.models import RagChunk, RagDocument
from src.utils.ai_client import embed
from src.tasks.models import TaskModel
from src.utils.settings import settings


def pdf_context(
    db: Session, user_id: int, question: str, document_id: int | None,
    *, guidelines_only: bool = False, language: str | None = None,
):
    document_scope = [
        RagDocument.user_id == user_id,
        RagDocument.status == "ready",
        RagDocument.embedding_model == settings.EMBEDDING_MODEL,
    ]
    if guidelines_only:
        document_scope.extend((
            RagDocument.user_id.in_(select(UserModel.id).where(UserModel.role == "super_admin")),
        ))
        if db.query(RagDocument.id).filter(*document_scope).first() is None:
            return "", []
    vector = embed([question])[0]
    distance = RagChunk.embedding.cosine_distance(vector)
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
            func.vector_dims(RagChunk.embedding) == len(vector),
        )
    )
    if document_id is not None:
        query = query.filter(RagDocument.id == document_id)

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
