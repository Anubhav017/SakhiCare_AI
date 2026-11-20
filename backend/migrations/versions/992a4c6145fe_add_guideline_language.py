"""Identify the language and topic of approved guidelines."""

import sqlalchemy as sa
from alembic import op

revision = "992a4c6145fe"
down_revision = "592121b7e136"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_documents", sa.Column("guideline_language", sa.String(2)))
    op.add_column("rag_documents", sa.Column("guideline_topic_key", sa.String(80)))
    op.create_check_constraint(
        "ck_rag_guideline_language", "rag_documents", "guideline_language IN ('hi', 'en')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_rag_guideline_language", "rag_documents", type_="check")
    op.drop_column("rag_documents", "guideline_topic_key")
    op.drop_column("rag_documents", "guideline_language")
