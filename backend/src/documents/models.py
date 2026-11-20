from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import deferred
from pgvector.sqlalchemy import Vector
from src.User.models import UserModel
from src.utils.db import Base

class RagDocument(Base):
    __tablename__ = "rag_documents"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(UserModel.id, ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    embedding_model = Column(String(255))
    sha256 = Column(String(64), nullable=False)
    pdf_data = deferred(Column(LargeBinary))
    status = Column(String(10), nullable=False, server_default="ready")
    attempts = Column(Integer, nullable=False, server_default="0")
    available_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lease_token = Column(String(32))
    indexing_error = Column(Text)
    guideline_title = Column(String(255))
    guideline_version = Column(String(100))
    guideline_language = Column(String(2))
    guideline_topic_key = Column(String(80))
    guideline_approved_at = Column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "sha256", name="uq_rag_user_hash"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_rag_document_status",
        ),
        CheckConstraint("guideline_language IN ('hi', 'en')", name="ck_rag_guideline_language"),
        Index("ix_rag_document_queue", "status", "available_at", "id"),
    )

class RagChunk(Base):
    __tablename__ = "rag_chunks"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("rag_documents.id", ondelete="CASCADE"), index=True)
    page = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(), nullable=False)
