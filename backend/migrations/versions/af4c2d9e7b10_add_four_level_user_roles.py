"""Move ASHA and Super Admin accounts to the four-level hierarchy."""

import sqlalchemy as sa
from alembic import op


revision = "af4c2d9e7b10"
down_revision = "4b8d61a2f903"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = "users"
    checks = {item["name"] for item in sa.inspect(op.get_bind()).get_check_constraints(table)}
    if "ck_users_role" in checks:
        op.drop_constraint("ck_users_role", table, type_="check")

    op.execute("UPDATE users SET role = 'user' WHERE role = 'asha'")
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'super_admin'")
    op.alter_column(table, "role", existing_type=sa.String(20), server_default="user", nullable=False)
    op.create_check_constraint(
        "ck_users_role", table, "role IN ('user', 'manager', 'executive', 'admin')",
    )


def downgrade() -> None:
    raise RuntimeError("Role hierarchy data cannot be safely downgraded to the two-role model.")
