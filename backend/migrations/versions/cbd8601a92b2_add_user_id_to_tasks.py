"""Initialize users and tasks, or adopt the existing schema."""

import sqlalchemy as sa
from alembic import op

revision = "cbd8601a92b2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = None if op.get_context().as_sql else sa.inspect(op.get_bind())

    if schema is None or not schema.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("username", sa.String(), nullable=False, unique=True),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=False, unique=True),
        )

    if schema is None or not schema.has_table("user_tasks"):
        op.create_table(
            "user_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("description", sa.String()),
            sa.Column("is_completed", sa.Boolean()),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        )
        return

    if "user_id" not in {column["name"] for column in schema.get_columns("user_tasks")}:
        # Keep legacy tasks without an owner. User-scoped queries exclude them.
        op.add_column("user_tasks", sa.Column("user_id", sa.Integer()))
        op.create_foreign_key(
            "fk_user_tasks_user_id_users",
            "user_tasks",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    # This revision can adopt pre-existing tables and ownership data.
    raise RuntimeError("The baseline is irreversible because it can adopt existing data.")
