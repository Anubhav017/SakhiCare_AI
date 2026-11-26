"""Add the separate in-house Super Admin role for client onboarding."""

import sqlalchemy as sa
from alembic import op


revision = "c6d72a108e45"
down_revision = "af4c2d9e7b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role", "users",
        "role IN ('user', 'manager', 'executive', 'admin', 'super_admin')",
    )
    op.create_index(
        "uq_users_single_super_admin", "users", ["role"],
        unique=True,
        postgresql_where=sa.text("role = 'super_admin'"),
        sqlite_where=sa.text("role = 'super_admin'"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_single_super_admin", table_name="users")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'manager', 'executive', 'admin')")
