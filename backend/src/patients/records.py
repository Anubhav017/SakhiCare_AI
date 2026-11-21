from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.followups.models import FollowupModel
from src.patients.controller import patient_scope
from src.patients.models import PatientModel
from src.User.models import UserModel


def read_records(db: Session, user: UserModel, question: str, worker: str | None = None):
    scope = patient_scope(user)
    if question == "patient_count" and user.role != "super_admin":
        count = db.scalar(select(func.count()).select_from(PatientModel).where(scope))
        return {"count": count}

    if question in ("patient_count", "patients_by_worker"):
        if user.role != "super_admin":
            raise HTTPException(403, "Super Admin access required")
        rows = db.execute(
            select(UserModel.name.label("worker"), func.count(PatientModel.id).label("count"))
            .outerjoin(PatientModel, PatientModel.asha_user_id == UserModel.id)
            .where(UserModel.role == "asha", UserModel.admin_id == user.id)
            .group_by(UserModel.id, UserModel.name)
            .order_by(UserModel.name, UserModel.id)
        )
        workers = [dict(row) for row in rows.mappings()]
        result = {"workers": workers}
        if question == "patient_count":
            result["count"] = sum(worker["count"] for worker in workers)
        return result

    if question == "worker_patients":
        if user.role != "super_admin":
            raise HTTPException(403, "Super Admin access required")
        if not worker or not worker.strip():
            raise HTTPException(422, "Enter the ASHA name or username")
        lookup = worker.strip().lower()
        team = select(UserModel).where(UserModel.role == "asha", UserModel.admin_id == user.id)
        selected = db.scalar(team.where(func.lower(UserModel.username) == lookup))
        if selected is None:
            matches = db.scalars(team.where(func.lower(UserModel.name) == lookup).limit(2)).all()
            if len(matches) > 1:
                raise HTTPException(409, "More than one ASHA has that name. Use their username.")
            if not matches:
                raise HTTPException(404, "No matching ASHA in your team. Try their full name or username.")
            selected = matches[0]
        query = select(PatientModel.id, PatientModel.name).where(scope, PatientModel.asha_user_id == selected.id)
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        results = db.execute(query.order_by(PatientModel.name, PatientModel.id).limit(50))
        return {"worker": selected.name, "total": total, "patients": [dict(row) for row in results.mappings()]}

    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    query = (
        select(
            FollowupModel.id, FollowupModel.patient_id, PatientModel.name.label("patient"),
            FollowupModel.title, FollowupModel.due_date,
        )
        .join(PatientModel, PatientModel.id == FollowupModel.patient_id)
        .where(scope, FollowupModel.is_completed.is_(False), FollowupModel.due_date <= today)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(FollowupModel.due_date, FollowupModel.id).limit(50))
    return {"total": total, "followups": [dict(row) for row in rows.mappings()]}
