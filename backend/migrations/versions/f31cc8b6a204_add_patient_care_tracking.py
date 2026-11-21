"""Store patient anemia assessments and referral history."""

import sqlalchemy as sa
from alembic import op

revision = "f31cc8b6a204"
down_revision = "bd72f2a09411"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("patients", sa.Column("anemia_status", sa.String(12), nullable=True))
    op.create_check_constraint("ck_patient_anemia_status", "patients", "anemia_status IN ('confirmed', 'not_anemic')")
    op.create_table(
        "patient_referrals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("facility", sa.String(120), nullable=False),
        sa.Column("referred_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("outcome", sa.String(500)),
        sa.CheckConstraint(
            "(status IN ('referred', 'attended') AND outcome IS NULL) OR "
            "(status = 'closed' AND outcome IS NOT NULL AND length(trim(outcome)) > 0)",
            name="ck_patient_referral_outcome",
        ),
    )
    op.create_index("ix_patient_referrals_patient_id", "patient_referrals", ["patient_id"])


def downgrade():
    raise RuntimeError("Downgrading would discard saved anemia assessments and referrals.")
