"""Create or update the single in-house SakhiCare Super Admin account."""

import os

from sqlalchemy import select

from src.User.controller import get_password_hash
from src.User.models import UserModel
from src.utils.db import Session


def main() -> None:
    username = os.environ.get("ONBOARDING_ADMIN_USERNAME", "sakhicare_super_admin").strip()
    email = os.environ.get("ONBOARDING_ADMIN_EMAIL", "onboarding-admin@sakhicare.local").strip().lower()
    password = os.environ.get("ONBOARDING_ADMIN_PASSWORD", "")
    name = os.environ.get("ONBOARDING_ADMIN_NAME", "SakhiCare Onboarding Admin").strip()
    if len(password) < 12:
        raise SystemExit("Set ONBOARDING_ADMIN_PASSWORD to a private password of at least 12 characters.")

    with Session.begin() as db:
        existing_super_admin = db.scalar(select(UserModel).where(UserModel.role == "super_admin"))
        if existing_super_admin is not None and existing_super_admin.username != username:
            raise SystemExit("A Super Admin already exists. Use its username or resolve it manually before replacing it.")
        account = db.scalar(select(UserModel).where(UserModel.username == username))
        email_owner = db.scalar(select(UserModel).where(UserModel.email == email))
        if email_owner is not None and (account is None or email_owner.id != account.id):
            raise SystemExit("The onboarding email is already assigned to a different account.")
        if account is None:
            account = UserModel(name=name, username=username, email=email, hashed_password="", role="super_admin")
            db.add(account)
        account.name = name
        account.email = email
        account.role = "super_admin"
        account.admin_id = None
        account.hashed_password = get_password_hash(password)

    print(f"SakhiCare Super Admin ready: {username}")
    print("Open /onboarding to create client Admin accounts.")


if __name__ == "__main__":
    main()
