from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.User.models import UserModel

ROLES = ("user", "manager", "executive", "admin")
SUPERVISOR_ROLES = ("manager", "executive", "admin")


def is_supervisor(user: UserModel) -> bool:
    return user.role in SUPERVISOR_ROLES


def managed_user_ids(user_id: int):
    descendants = select(UserModel.id.label("id")).where(
        UserModel.admin_id == user_id,
    ).cte("managed_users", recursive=True)
    descendants = descendants.union(
        select(UserModel.id).join(descendants, UserModel.admin_id == descendants.c.id)
    )
    return select(UserModel.id).join(descendants, UserModel.id == descendants.c.id).where(
        UserModel.role == "user",
    )


def managed_users(db: Session, user_id: int) -> list[UserModel]:
    return list(db.scalars(
        select(UserModel).where(UserModel.id.in_(managed_user_ids(user_id)))
        .order_by(UserModel.name, UserModel.id)
    ))


def managed_accounts(db: Session, user_id: int, *, include_unassigned: bool = False) -> list[dict]:
    descendants = select(
        UserModel.id.label("id"), UserModel.name.label("name"),
        UserModel.username.label("username"), UserModel.email.label("email"),
        UserModel.role.label("role"),
        UserModel.admin_id.label("reports_to_id"),
    ).where(UserModel.admin_id == user_id).cte("account_hierarchy", recursive=True)
    descendants = descendants.union(
        select(
            UserModel.id, UserModel.name, UserModel.username,
            UserModel.email, UserModel.role, UserModel.admin_id,
        ).join(descendants, UserModel.admin_id == descendants.c.id)
    )
    rows = [dict(row) for row in db.execute(select(descendants).order_by(
        descendants.c.role, descendants.c.name, descendants.c.id,
    )).mappings()]
    if include_unassigned:
        rows.extend(dict(row) for row in db.execute(select(
            UserModel.id, UserModel.name, UserModel.username, UserModel.email,
            UserModel.role, UserModel.admin_id.label("reports_to_id"),
        ).where(UserModel.admin_id.is_(None), UserModel.id != user_id, UserModel.role != "admin")
         .order_by(UserModel.role, UserModel.name, UserModel.id)).mappings())
    return rows


def update_member_access(db: Session, admin_id: int, member_id: int, role: str,
                         reports_to_id: int) -> UserModel:
    # The hierarchy endpoint's source query authorizes IDs against this Admin's
    # descendants; never trust a reporting-manager ID supplied by the browser.
    descendants = managed_accounts(db, admin_id)
    descendant_ids = {row["id"] for row in descendants}
    unassigned = managed_accounts(db, admin_id, include_unassigned=True)
    workspace_ids = {row["id"] for row in unassigned}
    if member_id not in workspace_ids:
        raise HTTPException(404, "Person not found in this workspace")
    member = db.scalar(select(UserModel).where(UserModel.id == member_id).with_for_update())
    if member is None:
        raise HTTPException(404, "Person not found")
    if member.role == "admin":
        raise HTTPException(403, "Admin accounts cannot be reassigned from this workspace")

    parent = db.scalar(select(UserModel).where(UserModel.id == reports_to_id).with_for_update())
    if parent is None or (parent.id != admin_id and parent.id not in descendant_ids):
        raise HTTPException(422, "Choose a reporting manager in this workspace")
    expected_parent_role = {"executive": "admin", "manager": "executive", "user": "manager"}[role]
    if parent.role != expected_parent_role:
        raise HTTPException(422, f"A {role} must report to a {expected_parent_role}")

    descendants_cte = select(UserModel.id.label("id")).where(
        UserModel.admin_id == member_id,
    ).cte("member_descendants", recursive=True)
    descendants_cte = descendants_cte.union(
        select(UserModel.id).join(descendants_cte, UserModel.admin_id == descendants_cte.c.id)
    )
    if reports_to_id == member_id or reports_to_id in set(db.scalars(select(descendants_cte.c.id))):
        raise HTTPException(422, "A person cannot report to themselves or someone below them")

    child_role = {"admin": "executive", "executive": "manager", "manager": "user"}
    children = list(db.scalars(select(UserModel).where(UserModel.admin_id == member_id)))
    if any(child.role != child_role.get(role) for child in children):
        raise HTTPException(409, "Move this person's direct reports before changing their role")

    member.role = role
    member.admin_id = reports_to_id
    db.commit()
    db.refresh(member)
    return member


def root_admin_id(db: Session, user: UserModel) -> int | None:
    current = user
    seen: set[int] = set()
    while current.id not in seen:
        seen.add(current.id)
        if current.role == "admin":
            return current.id
        if current.admin_id is None:
            return None
        parent = db.get(UserModel, current.admin_id)
        if parent is None:
            return None
        current = parent
    return None
