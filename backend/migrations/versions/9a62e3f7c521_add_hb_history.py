"""Preserve measured Hb readings."""

from alembic import op
import sqlalchemy as sa

revision = "9a62e3f7c521"
down_revision = "7dd6295175a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_hb_readings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("hb", sa.Float, nullable=False),
        sa.Column("method", sa.String(100), nullable=False),
        sa.UniqueConstraint("patient_id", "date", "hb", "method", name="uq_patient_hb_reading"),
        if_not_exists=True,
    )
    op.execute("""
        INSERT INTO patient_hb_readings (patient_id, date, hb, method)
        SELECT patient_id, date, hb, method FROM patient_screenings WHERE hb IS NOT NULL
        ON CONFLICT ON CONSTRAINT uq_patient_hb_reading DO NOTHING
    """)


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard Hb history.")
