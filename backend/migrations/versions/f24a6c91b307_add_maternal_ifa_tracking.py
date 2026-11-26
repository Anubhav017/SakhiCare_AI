"""Add pregnancy, ANC, and ASHA-recorded IFA tracking."""

from alembic import op
import sqlalchemy as sa


revision = "f24a6c91b307"
down_revision = "e6b2c01d9a44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_pregnancies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lmp_date", sa.Date()),
        sa.Column("edd_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="active", nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'completed', 'closed')", name="ck_patient_pregnancy_status"),
        if_not_exists=True,
    )
    op.create_index("ix_patient_pregnancies_patient_id", "patient_pregnancies", ["patient_id"], if_not_exists=True)
    op.create_index("ix_patient_pregnancies_status", "patient_pregnancies", ["status"], if_not_exists=True)
    op.create_index("ix_patient_pregnancies_recorded_by_user_id", "patient_pregnancies", ["recorded_by_user_id"], if_not_exists=True)
    op.create_index(
        "uq_patient_pregnancy_active",
        "patient_pregnancies",
        ["patient_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    if_not_exists=True,
    )

    op.create_table(
        "patient_anc_visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pregnancy_id", sa.Integer(), sa.ForeignKey("patient_pregnancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("followup_id", sa.Integer(), sa.ForeignKey("patient_followups.id", ondelete="SET NULL"), unique=True),
        sa.Column("status", sa.String(length=12), server_default="planned", nullable=False),
        sa.Column("facility", sa.String(length=120)),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('planned', 'completed', 'cancelled')", name="ck_patient_anc_visit_status"),
        if_not_exists=True,
    )
    op.create_index("ix_patient_anc_visits_pregnancy_id", "patient_anc_visits", ["pregnancy_id"], if_not_exists=True)
    op.create_index("ix_patient_anc_visits_status", "patient_anc_visits", ["status"], if_not_exists=True)
    op.create_index("ix_patient_anc_visits_recorded_by_user_id", "patient_anc_visits", ["recorded_by_user_id"], if_not_exists=True)

    op.create_table(
        "patient_ifa_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pregnancy_id", sa.Integer(), sa.ForeignKey("patient_pregnancies.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("directions", sa.String(length=240), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        if_not_exists=True,
    )
    op.create_index("ix_patient_ifa_plans_recorded_by_user_id", "patient_ifa_plans", ["recorded_by_user_id"], if_not_exists=True)

    op.create_table(
        "patient_ifa_intake_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pregnancy_id", sa.Integer(), sa.ForeignKey("patient_pregnancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intake_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('taken', 'missed', 'unknown')", name="ck_patient_ifa_intake_status"),
        sa.UniqueConstraint("pregnancy_id", "intake_date", name="uq_patient_ifa_intake_day"),
        if_not_exists=True,
    )
    op.create_index("ix_patient_ifa_intake_logs_pregnancy_id", "patient_ifa_intake_logs", ["pregnancy_id"], if_not_exists=True)
    op.create_index("ix_patient_ifa_intake_logs_recorded_by_user_id", "patient_ifa_intake_logs", ["recorded_by_user_id"], if_not_exists=True)


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard pregnancy, ANC, and IFA records.")
