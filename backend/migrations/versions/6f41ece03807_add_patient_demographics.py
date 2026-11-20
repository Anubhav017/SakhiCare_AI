"""Keep optional village and age with the assigned patient."""

import sqlalchemy as sa
from alembic import op

revision = "6f41ece03807"
down_revision = "756a4a0311ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("village", sa.String(100)), if_not_exists=True)
    op.add_column("patients", sa.Column("age", sa.Integer()), if_not_exists=True)


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard saved patient demographics.")
