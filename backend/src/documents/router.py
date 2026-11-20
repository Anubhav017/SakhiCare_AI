from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from src.documents.ingestion import enqueue_pdf
from src.documents.models import RagChunk, RagDocument
from src.documents.schemas import DocumentDetail, DocumentSummary, DocumentUploadResponse, GuidelineApproval
from src.User.models import UserModel
from src.utils.db import get_db
from src.utils.helpers import is_authenticated
from src.utils.settings import settings

documents_router = APIRouter(prefix="/api", tags=["Documents"])


@documents_router.post(
    "/rag/upload", status_code=202, response_model=DocumentUploadResponse,
    responses={200: {"model": DocumentUploadResponse, "description": "Already indexed"}},
)
def upload_pdf(
    response: Response,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: UserModel = Depends(is_authenticated),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a .pdf file")
    data = file.file.read(settings.RAG_MAX_UPLOAD_BYTES + 1)
    upload = enqueue_pdf(db, user.id, file.filename, data)
    response.headers["Location"] = f"/api/rag/documents/{upload.document_id}"
    if upload.status == "ready":
        response.status_code = 200
    return upload


@documents_router.get("/rag/documents", response_model=list[DocumentSummary])
def documents(
    db: Session = Depends(get_db),
    user: UserModel = Depends(is_authenticated),
):
    return (
        db.query(
            RagDocument.id, RagDocument.filename, RagDocument.status,
            RagDocument.guideline_language, RagDocument.guideline_topic_key,
        )
        .filter(RagDocument.user_id == user.id)
        .order_by(RagDocument.id.desc())
        .all()
    )


@documents_router.get("/rag/documents/{document_id}", response_model=DocumentDetail)
def document_status(
    document_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(is_authenticated),
):
    document = db.query(RagDocument).filter_by(id=document_id, user_id=user.id).first()
    if document is None:
        raise HTTPException(404, "Document not found")
    chunks = 0
    if document.status == "ready":
        chunks = db.query(RagChunk.id).filter_by(document_id=document_id).count()
    return DocumentDetail(
        id=document.id, filename=document.filename, status=document.status,
        guideline_language=document.guideline_language,
        guideline_topic_key=document.guideline_topic_key,
        chunks=chunks, indexing_error=document.indexing_error,
    )


def _owned_guideline(document_id: int, user: UserModel, db: Session) -> RagDocument:
    if user.role != "super_admin":
        raise HTTPException(403, "Super Admin access required")
    document = (
        db.query(RagDocument)
        .filter_by(id=document_id, user_id=user.id)
        .with_for_update()
        .first()
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


@documents_router.put("/rag/documents/{document_id}/guideline", response_model=GuidelineApproval)
def update_guideline_metadata(
    document_id: int, body: GuidelineApproval, db: Session = Depends(get_db),
    user: UserModel = Depends(is_authenticated),
):
    document = _owned_guideline(document_id, user, db)
    if document.status != "ready" or document.embedding_model != settings.EMBEDDING_MODEL:
        raise HTTPException(409, "The guideline must be indexed with the current embedding model first")
    document.guideline_title = body.title
    document.guideline_version = body.version
    if "language" in body.model_fields_set:
        document.guideline_language = body.language
    if "topic_key" in body.model_fields_set:
        document.guideline_topic_key = body.topic_key
    metadata = GuidelineApproval(
        title=body.title, version=body.version,
        language=document.guideline_language, topic_key=document.guideline_topic_key,
    )
    db.commit()
    return metadata
