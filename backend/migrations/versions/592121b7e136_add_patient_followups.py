"""Persist patient-linked follow-ups."""

import sqlalchemy as sa
from alembic import op

revision = "592121b7e136"
down_revision = "41b80a89c6cf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_followups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        if_not_exists=True,
    )
    op.create_index("ix_patient_followups_patient_due", "patient_followups", ["patient_id", "due_date"], if_not_exists=True)


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard patient follow-ups.")
