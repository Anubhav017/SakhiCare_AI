"""Track registration timestamps for dashboard summaries."""

import sqlalchemy as sa
from alembic import op

from migrations.compat import add_column_if_missing

revision = "58e2b17a9d40"
down_revision = "f31cc8b6a204"
branch_labels = None
depends_on = None


def upgrade():
    add_column_if_missing("patients", sa.Column("registered_at", sa.DateTime(timezone=True)))
    op.alter_column("patients", "registered_at", existing_type=sa.DateTime(timezone=True), server_default=sa.func.now())


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard saved patient registration timestamps.")
