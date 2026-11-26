
"""Persist original PDFs and add durable indexing state."""

from alembic import op
import sqlalchemy as sa

revision = "38bc98ad5820"
down_revision = "0067f3a21c09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_name = "rag_documents"

    # Add missing columns only.
    existing_columns = {
        column["name"]
        for column in inspector.get_columns(table_name)
    }

    columns_to_add = [
        sa.Column("pdf_data", sa.LargeBinary()),
        sa.Column(
            "status",
            sa.String(10),
            nullable=False,
            server_default="ready",
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("lease_token", sa.String(32)),
        sa.Column("indexing_error", sa.Text()),
    ]

    for column in columns_to_add:
        if column.name not in existing_columns:
            op.add_column(table_name, column)

    # Add check constraint only if missing.
    existing_constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints(table_name)
    }

    constraint_name = "ck_rag_document_status"

    if constraint_name not in existing_constraints:
        op.create_check_constraint(
            constraint_name,
            table_name,
            "status IN ('pending', 'processing', 'ready', 'failed')",
        )

    # Add index only if missing.
    existing_indexes = {
        index["name"]
        for index in inspector.get_indexes(table_name)
    }

    index_name = "ix_rag_document_queue"

    if index_name not in existing_indexes:
        op.create_index(
            index_name,
            table_name,
            ["status", "available_at", "id"],
        )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrading would discard original PDFs and indexing jobs."
    )
