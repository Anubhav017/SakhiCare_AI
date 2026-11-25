"""Add structured state, district, block, village and urban ward address fields."""

import sqlalchemy as sa
from alembic import op

revision = "4b8d61a2f903"
down_revision = "f24a6c91b307"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("patients", sa.Column("state", sa.String(100), nullable=True))
    op.add_column("patients", sa.Column("district", sa.String(120), nullable=True))
    op.add_column("patients", sa.Column("block", sa.String(120), nullable=True))
    op.add_column("patients", sa.Column("locality_type", sa.String(10), nullable=True))
    op.add_column("patients", sa.Column("town", sa.String(120), nullable=True))
    op.add_column("patients", sa.Column("ward", sa.String(30), nullable=True))
    op.create_check_constraint("ck_patient_locality_type", "patients", "locality_type IN ('village', 'ward')")


def downgrade():
    op.drop_constraint("ck_patient_locality_type", "patients", type_="check")
    for column in ("ward", "town", "locality_type", "block", "district", "state"):
        op.drop_column("patients", column)
