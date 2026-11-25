"""Add patient consent capture and audit events."""
from alembic import op
import sqlalchemy as sa

revision = "c39a8f5d10e2"
down_revision = "58e2b17a9d40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("consent_obtained", sa.Boolean(), nullable=True))
    op.add_column("patients", sa.Column("consent_recorded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("patients", sa.Column("consent_recorded_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_patients_consent_recorded_by_users", "patients", "users",
        ["consent_recorded_by"], ["id"], ondelete="SET NULL",
    )
    op.create_table(
        "patient_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_patient_audit_events_patient_id", "patient_audit_events", ["patient_id"])
    op.create_index("ix_patient_audit_events_actor_user_id", "patient_audit_events", ["actor_user_id"])
    op.create_index("ix_patient_audit_events_created_at", "patient_audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_patient_audit_events_created_at", table_name="patient_audit_events")
    op.drop_index("ix_patient_audit_events_actor_user_id", table_name="patient_audit_events")
    op.drop_index("ix_patient_audit_events_patient_id", table_name="patient_audit_events")
    op.drop_table("patient_audit_events")
    op.drop_constraint("fk_patients_consent_recorded_by_users", "patients", type_="foreignkey")
    op.drop_column("patients", "consent_recorded_by")
    op.drop_column("patients", "consent_recorded_at")
    op.drop_column("patients", "consent_obtained")
