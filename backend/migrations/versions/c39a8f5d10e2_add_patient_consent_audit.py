"""Add patient consent capture and audit events."""
from alembic import op

from migrations.compat import add_column_if_missing, create_fk_if_missing
import sqlalchemy as sa

revision = "c39a8f5d10e2"
down_revision = "58e2b17a9d40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_missing("patients", sa.Column("consent_obtained", sa.Boolean(), nullable=True))
    add_column_if_missing("patients", sa.Column("consent_recorded_at", sa.DateTime(timezone=True), nullable=True))
    add_column_if_missing("patients", sa.Column("consent_recorded_by", sa.Integer(), nullable=True))
    create_fk_if_missing("patients", "fk_patients_consent_recorded_by_users", "users", ["consent_recorded_by"], ["id"], ondelete="SET NULL")
    op.create_table(
        "patient_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        if_not_exists=True,
    )
    op.create_index("ix_patient_audit_events_patient_id", "patient_audit_events", ["patient_id"], if_not_exists=True)
    op.create_index("ix_patient_audit_events_actor_user_id", "patient_audit_events", ["actor_user_id"], if_not_exists=True)
    op.create_index("ix_patient_audit_events_created_at", "patient_audit_events", ["created_at"], if_not_exists=True)


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard patient consent and activity history.")
