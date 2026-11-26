"""Add structured state, district, block, village and urban ward address fields."""

import sqlalchemy as sa
from alembic import op

revision = "4b8d61a2f903"
down_revision = "f24a6c91b307"
branch_labels = None
depends_on = None


def upgrade():
    table_name = "patients"
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}

    address_columns = (
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("district", sa.String(120), nullable=True),
        sa.Column("block", sa.String(120), nullable=True),
        sa.Column("locality_type", sa.String(10), nullable=True),
        sa.Column("town", sa.String(120), nullable=True),
        sa.Column("ward", sa.String(30), nullable=True),
    )
    for column in address_columns:
        if column.name not in existing_columns:
            op.add_column(table_name, column)

    constraint_name = "ck_patient_locality_type"
    existing_constraints = {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_check_constraints(table_name)
    }
    if constraint_name not in existing_constraints:
        op.create_check_constraint(
            constraint_name, table_name, "locality_type IN ('village', 'ward')"
        )


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard saved patient address details.")
