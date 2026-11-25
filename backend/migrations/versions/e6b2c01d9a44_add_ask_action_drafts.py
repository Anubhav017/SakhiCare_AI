"""Add durable Ask action drafts and reversible follow-up cancellation."""
from alembic import op
import sqlalchemy as sa


revision = "e6b2c01d9a44"
down_revision = "d4a8c1b72f03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patient_followups",
        sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "ask_action_drafts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("preview", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'cancelled', 'expired', 'failed')",
            name="ck_ask_action_draft_status",
        ),
    )
    op.create_index("ix_ask_action_drafts_actor_user_id", "ask_action_drafts", ["actor_user_id"])
    op.create_index("ix_ask_action_drafts_patient_id", "ask_action_drafts", ["patient_id"])
    op.create_index("ix_ask_action_drafts_status", "ask_action_drafts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ask_action_drafts_status", table_name="ask_action_drafts")
    op.drop_index("ix_ask_action_drafts_patient_id", table_name="ask_action_drafts")
    op.drop_index("ix_ask_action_drafts_actor_user_id", table_name="ask_action_drafts")
    op.drop_table("ask_action_drafts")
    op.drop_column("patient_followups", "is_archived")
