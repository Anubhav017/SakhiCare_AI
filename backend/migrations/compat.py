"""Small schema-inspection helpers for migrations that adopt existing databases."""

import sqlalchemy as sa
from alembic import op


def add_column_if_missing(table: str, column: sa.Column) -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in columns:
        op.add_column(table, column)


def create_check_if_missing(table: str, name: str, condition: str) -> None:
    checks = {item["name"] for item in sa.inspect(op.get_bind()).get_check_constraints(table)}
    if name not in checks:
        op.create_check_constraint(name, table, condition)


def create_fk_if_missing(
    table: str,
    name: str,
    referred_table: str,
    columns: list[str],
    referred_columns: list[str],
    ondelete: str | None = None,
) -> None:
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys(table)
    present = any(
        item.get("constrained_columns") == columns
        and item.get("referred_table") == referred_table
        and item.get("referred_columns") == referred_columns
        for item in foreign_keys
    )
    if not present:
        op.create_foreign_key(
            name, table, referred_table, columns, referred_columns, ondelete=ondelete
        )
