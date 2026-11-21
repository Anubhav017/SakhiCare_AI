"""Track registration timestamps for dashboard summaries."""

import sqlalchemy as sa
from alembic import op

revision = "58e2b17a9d40"
down_revision = "f31cc8b6a204"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("patients", sa.Column("registered_at", sa.DateTime(timezone=True)))
    op.alter_column("patients", "registered_at", server_default=sa.func.now())


def downgrade():
    op.drop_column("patients", "registered_at")
