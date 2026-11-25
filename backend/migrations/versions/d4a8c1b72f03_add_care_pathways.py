"""Add persistent Care Pathway runs and steps."""
from alembic import op
import sqlalchemy as sa


revision = "d4a8c1b72f03"
down_revision = ("f31cc8b6a204", "c39a8f5d10e2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "care_pathway_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pathway_key", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("source_key", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="active", nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'completed', 'paused', 'cancelled')", name="ck_care_pathway_run_status"),
        sa.UniqueConstraint("source_key", name="uq_care_pathway_source_key"),
    )
    op.create_index("ix_care_pathway_runs_patient_id", "care_pathway_runs", ["patient_id"])
    op.create_index("ix_care_pathway_runs_status", "care_pathway_runs", ["status"])
    op.create_index("ix_care_pathway_runs_created_by_user_id", "care_pathway_runs", ["created_by_user_id"])
    op.create_table(
        "care_pathway_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("care_pathway_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.CheckConstraint("status IN ('pending', 'completed', 'skipped')", name="ck_care_pathway_step_status"),
        sa.UniqueConstraint("run_id", "position", name="uq_care_pathway_step_position"),
    )
    op.create_index("ix_care_pathway_steps_run_id", "care_pathway_steps", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_care_pathway_steps_run_id", table_name="care_pathway_steps")
    op.drop_table("care_pathway_steps")
    op.drop_index("ix_care_pathway_runs_created_by_user_id", table_name="care_pathway_runs")
    op.drop_index("ix_care_pathway_runs_status", table_name="care_pathway_runs")
    op.drop_index("ix_care_pathway_runs_patient_id", table_name="care_pathway_runs")
    op.drop_table("care_pathway_runs")
