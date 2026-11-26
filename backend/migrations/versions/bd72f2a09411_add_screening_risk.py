"""Store manually recorded screening risk."""

from alembic import op
import sqlalchemy as sa

revision = "bd72f2a09411"
down_revision = "a7b4d8c021e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "patient_screenings",
        sa.Column("risk", sa.String(8), nullable=True),
        if_not_exists=True,
    )
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_screening_risk'
                AND conrelid = 'patient_screenings'::regclass
            ) THEN
                ALTER TABLE patient_screenings ADD CONSTRAINT ck_screening_risk
                CHECK (risk IN ('low', 'moderate', 'high'));
            END IF;
        END $$;
    """)


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard recorded screening risk.")
