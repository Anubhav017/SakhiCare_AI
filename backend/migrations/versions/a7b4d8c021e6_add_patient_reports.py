"""Store patient PDF reports."""

from alembic import op
import sqlalchemy as sa

revision = "a7b4d8c021e6"
down_revision = "9a62e3f7c521"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "patient_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("pdf", sa.LargeBinary(), nullable=False),
    )


def downgrade():
    op.drop_table("patient_reports")
