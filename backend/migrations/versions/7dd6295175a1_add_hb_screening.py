"""Store the current Hb screening for each patient."""

from alembic import op
import sqlalchemy as sa

revision = "7dd6295175a1"
down_revision = "992a4c6145fe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_screenings",
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("hb", sa.Float),
        sa.Column("method", sa.String(100), nullable=False),
        sa.CheckConstraint(
            "(hb IS NULL AND method = '') OR (hb IS NOT NULL AND hb > 0 AND hb < 'Infinity'::float8 AND length(trim(method)) > 0)",
            name="ck_patient_screening_measurement",
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard recorded Hb screenings.")
