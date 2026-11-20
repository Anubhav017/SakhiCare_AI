"""Add ASHA roles and their supervising administrator."""

import sqlalchemy as sa
from alembic import op

revision = "811f23ad1feb"
down_revision = "6f41ece03807"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(20), nullable=False, server_default="asha"))
    op.add_column("users", sa.Column("admin_id", sa.Integer()))
    op.create_check_constraint("ck_users_role", "users", "role IN ('asha', 'super_admin')")
    op.create_foreign_key(
        "fk_users_admin_id_users", "users", "users", ["admin_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_users_admin_id", "users", ["admin_id"])


def downgrade() -> None:
    op.drop_index("ix_users_admin_id", table_name="users")
    op.drop_constraint("fk_users_admin_id_users", "users", type_="foreignkey")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "admin_id")
    op.drop_column("users", "role")
