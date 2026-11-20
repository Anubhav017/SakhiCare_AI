"""Add patient records assigned to ASHA worker accounts."""

from alembic import op
import sqlalchemy as sa

revision = "756a4a0311ce"
down_revision = "38bc98ad5820"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("asha_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        if_not_exists=True,
    )
    op.create_index("ix_patients_asha_user_id", "patients", ["asha_user_id"], if_not_exists=True)


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard patient records.")
