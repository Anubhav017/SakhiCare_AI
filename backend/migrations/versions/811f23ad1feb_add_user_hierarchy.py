"""Add ASHA roles and their supervising administrator; adopt existing fields."""

import sqlalchemy as sa
from alembic import op

revision = "811f23ad1feb"
down_revision = "6f41ece03807"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table_name = "users"
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"]: column for column in inspector.get_columns(table_name)}

    if "role" not in existing_columns:
        op.add_column(
            table_name,
            sa.Column("role", sa.String(20), nullable=False, server_default="asha"),
        )
    else:
        op.execute(sa.text("UPDATE users SET role = 'asha' WHERE role IS NULL"))
        role_column = existing_columns["role"]
        if role_column.get("nullable", True):
            op.alter_column(table_name, "role", existing_type=sa.String(20), nullable=False)
        if role_column.get("default") is None:
            op.alter_column(
                table_name, "role", existing_type=sa.String(20), server_default="asha"
            )

    existing_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
    if "admin_id" not in existing_columns:
        op.add_column(table_name, sa.Column("admin_id", sa.Integer(), nullable=True))

    inspector = sa.inspect(op.get_bind())
    check_names = {item["name"] for item in inspector.get_check_constraints(table_name)}
    if "ck_users_role" not in check_names:
        op.create_check_constraint(
            "ck_users_role", table_name, "role IN ('asha', 'super_admin')"
        )

    inspector = sa.inspect(op.get_bind())
    foreign_keys = inspector.get_foreign_keys(table_name)
    has_admin_fk = any(
        item.get("constrained_columns") == ["admin_id"]
        and item.get("referred_table") == table_name
        and item.get("referred_columns") == ["id"]
        for item in foreign_keys
    )
    if not has_admin_fk:
        op.create_foreign_key(
            "fk_users_admin_id_users", table_name, table_name,
            ["admin_id"], ["id"], ondelete="SET NULL",
        )

    index_names = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if "ix_users_admin_id" not in index_names:
        op.create_index("ix_users_admin_id", table_name, ["admin_id"])


def downgrade() -> None:
    raise RuntimeError("This revision may adopt existing user role data and cannot be safely reversed.")
