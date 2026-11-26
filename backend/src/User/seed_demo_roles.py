"""Create local Demo Executive and Manager accounts under Anubhav's Admin."""

import os

from sqlalchemy import select

from src.User.controller import get_password_hash
from src.User.models import UserModel
from src.utils.db import Session


def _upsert(db, *, name: str, username: str, email: str, role: str,
            password: str, parent_id: int) -> UserModel:
    account = db.scalar(select(UserModel).where(UserModel.username == username))
    if account is None:
        account = UserModel(
            name=name, username=username, email=email, role=role,
            hashed_password=get_password_hash(password), admin_id=parent_id,
        )
        db.add(account)
        db.flush()
    else:
        account.name = name
        account.email = email
        account.role = role
        account.admin_id = parent_id
        account.hashed_password = get_password_hash(password)
    return account


def main() -> None:
    password = os.environ.get("DEMO_ACCOUNT_PASSWORD", "")
    if len(password) < 8:
        raise SystemExit("Set DEMO_ACCOUNT_PASSWORD to a password of at least 8 characters.")

    with Session.begin() as db:
        admins = list(db.scalars(select(UserModel).where(UserModel.role == "admin")))
        admin = next((item for item in admins if "anubhav" in item.name.casefold()), None)
        if admin is None:
            if len(admins) != 1:
                raise SystemExit("Could not identify Anubhav's Admin account; review Admin users first.")
            admin = admins[0]
        executive = _upsert(
            db, name="Demo Executive", username="demo_executive",
            email="demo.executive@sakhicare.local", role="executive",
            password=password, parent_id=admin.id,
        )
        manager = _upsert(
            db, name="Demo Manager", username="demo_manager",
            email="demo.manager@sakhicare.local", role="manager",
            password=password, parent_id=executive.id,
        )
        db.query(UserModel).filter(
            UserModel.role == "user", UserModel.admin_id == admin.id,
        ).update({UserModel.admin_id: manager.id}, synchronize_session=False)

    print("Role hierarchy ready: Anubhav (admin) → demo_executive → demo_manager → ASHA users.")
    print("Demo usernames: demo_executive, demo_manager. Both use DEMO_ACCOUNT_PASSWORD.")


if __name__ == "__main__":
    main()
