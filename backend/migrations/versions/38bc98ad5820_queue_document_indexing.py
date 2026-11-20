"""Persist original PDFs and add durable indexing state."""

from alembic import op
import sqlalchemy as sa

revision = "38bc98ad5820"
down_revision = "0067f3a21c09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_documents", sa.Column("pdf_data", sa.LargeBinary()))
    op.add_column("rag_documents", sa.Column("status", sa.String(10), nullable=False, server_default="ready"))
    op.add_column("rag_documents", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("rag_documents", sa.Column(
        "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ))
    op.add_column("rag_documents", sa.Column("lease_token", sa.String(32)))
    op.add_column("rag_documents", sa.Column("indexing_error", sa.Text()))
    op.create_check_constraint(
        "ck_rag_document_status", "rag_documents",
        "status IN ('pending', 'processing', 'ready', 'failed')",
    )
    op.create_index("ix_rag_document_queue", "rag_documents", ["status", "available_at", "id"])


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard original PDFs and indexing jobs.")
