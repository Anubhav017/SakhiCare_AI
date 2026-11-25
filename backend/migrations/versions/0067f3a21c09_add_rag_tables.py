"""Enable pgvector and prepare document storage for embedding vectors."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0067f3a21c09"
down_revision = "cbd8601a92b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    schema = None if op.get_context().as_sql else sa.inspect(op.get_bind())

    if schema is None or not schema.has_table("rag_documents"):
        op.create_table(
            "rag_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("embedding_model", sa.String(255)),
            sa.UniqueConstraint("user_id", "sha256", name="uq_rag_user_hash"),
        )
    elif "embedding_model" not in {column["name"] for column in schema.get_columns("rag_documents")}:
        op.add_column("rag_documents", sa.Column("embedding_model", sa.String(255)))

    if schema is None or not schema.has_table("rag_chunks"):
        op.create_table(
            "rag_chunks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("rag_documents.id", ondelete="CASCADE")),
            sa.Column("page", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("embedding", Vector(), nullable=False),
        )
    else:
        op.alter_column("rag_chunks", "embedding", type_=Vector())

    op.create_index("ix_rag_documents_user_id", "rag_documents", ["user_id"], if_not_exists=True)
    op.create_index("ix_rag_chunks_document_id", "rag_chunks", ["document_id"], if_not_exists=True)


def downgrade() -> None:
    raise RuntimeError("This revision can adopt existing documents and embeddings.")
