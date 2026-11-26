"""Identify the language and topic of approved guidelines."""

import sqlalchemy as sa
from alembic import op

from migrations.compat import add_column_if_missing, create_check_if_missing

revision = "992a4c6145fe"
down_revision = "592121b7e136"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_missing("rag_documents", sa.Column("guideline_language", sa.String(2)))
    add_column_if_missing("rag_documents", sa.Column("guideline_topic_key", sa.String(80)))
    create_check_if_missing("rag_documents", "ck_rag_guideline_language", "guideline_language IN ('hi', 'en')")


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard saved guideline language and topic metadata.")
