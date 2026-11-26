"""Track approval and version metadata for guideline PDFs."""

import sqlalchemy as sa
from alembic import op

revision = "41b80a89c6cf"
down_revision = "811f23ad1feb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_documents", sa.Column("guideline_title", sa.String(255)), if_not_exists=True)
    op.add_column("rag_documents", sa.Column("guideline_version", sa.String(100)), if_not_exists=True)
    op.add_column(
        "rag_documents", sa.Column("guideline_approved_at", sa.DateTime(timezone=True)),
        if_not_exists=True,
    )


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard saved guideline approval metadata.")
