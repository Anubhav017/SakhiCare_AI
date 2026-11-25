from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.User.models import UserModel
from src.patients.models import PatientAuditEvent, PatientModel, PatientReferral, PatientScreening
from src.pathways.models import CarePathwayRun, CarePathwayStep


def _patient_scope(user: UserModel):
    if user.role == "super_admin":
        return PatientModel.asha_user_id.in_(
            select(UserModel.id).where(UserModel.role == "asha", UserModel.admin_id == user.id)
        )
    return PatientModel.asha_user_id == user.id


def _create_run(db: Session, user: UserModel, patient_id: int, pathway_key: str, title: str,
                source_key: str, step_titles: tuple[str, ...]) -> CarePathwayRun:
    existing = db.scalar(select(CarePathwayRun).where(CarePathwayRun.source_key == source_key))
    if existing is not None:
        return existing
    run = CarePathwayRun(
        patient_id=patient_id, pathway_key=pathway_key, title=title,
        source_key=source_key, created_by_user_id=user.id,
    )
    run.steps = [CarePathwayStep(position=index, title=step_title) for index, step_title in enumerate(step_titles, 1)]
    db.add(run)
    db.flush()
    return run


def start_screening_pathway(db: Session, user: UserModel, patient_id: int, screening: PatientScreening):
    if screening.hb is None or screening.risk not in {"high", "moderate"}:
        return None
    source_key = f"screening:{patient_id}:{screening.date.isoformat()}:{screening.hb}:{screening.risk}"
    return _create_run(
        db, user, patient_id, "hb_follow_up", "Hb result follow-up", source_key,
        (
            "Review the recorded Hb result against the team's approved protocol",
            "Discuss the result with the ANM or qualified clinician when needed",
            "Record the agreed next contact or care step",
        ),
    )


def start_referral_pathway(db: Session, user: UserModel, referral: PatientReferral):
    return _create_run(
        db, user, referral.patient_id, "referral_tracking", "Referral follow-up",
        f"referral:{referral.id}",
        (
            "Confirm the patient received the referral facility and visit details",
            "Check whether the patient attended the referred facility",
            "Record the referral outcome or the next follow-up plan",
        ),
    )


def sync_referral_pathway(db: Session, user: UserModel, referral: PatientReferral):
    run = db.scalar(
        select(CarePathwayRun).options(selectinload(CarePathwayRun.steps))
        .where(CarePathwayRun.source_key == f"referral:{referral.id}")
        .with_for_update()
    )
    if run is None:
        return
    now = datetime.now(timezone.utc)
    completed_positions = {1, 2} if referral.status == "attended" else {1, 2, 3} if referral.status == "closed" else set()
    for step in run.steps:
        if step.position in completed_positions:
            step.status = "completed"
            step.completed_at = step.completed_at or now
            step.completed_by_user_id = step.completed_by_user_id or user.id
    run.status = "completed" if referral.status == "closed" else "active"
    run.updated_at = now


def list_pathways(db: Session, user: UserModel, patient_id: int | None = None):
    query = (
        select(CarePathwayRun)
        .join(PatientModel, PatientModel.id == CarePathwayRun.patient_id)
        .options(selectinload(CarePathwayRun.steps))
        .where(_patient_scope(user))
    )
    if patient_id is not None:
        query = query.where(CarePathwayRun.patient_id == patient_id)
    return list(db.scalars(query.order_by(CarePathwayRun.status, CarePathwayRun.updated_at.desc(), CarePathwayRun.id.desc())))


def update_step(db: Session, user: UserModel, run_id: int, step_id: int, completed: bool):
    query = (
        select(CarePathwayRun)
        .join(PatientModel, PatientModel.id == CarePathwayRun.patient_id)
        .options(selectinload(CarePathwayRun.steps))
        .where(CarePathwayRun.id == run_id, _patient_scope(user))
        .with_for_update()
    )
    run = db.scalar(query)
    if run is None:
        raise HTTPException(404, "Care pathway not found")
    if user.role != "asha":
        raise HTTPException(403, "Only the assigned ASHA worker can update pathway steps")
    step = next((item for item in run.steps if item.id == step_id), None)
    if step is None:
        raise HTTPException(404, "Care pathway step not found")
    if run.status in {"cancelled", "paused"}:
        raise HTTPException(409, "Resume the care pathway before updating its steps")
    step.status = "completed" if completed else "pending"
    step.completed_at = datetime.now(timezone.utc) if completed else None
    step.completed_by_user_id = user.id if completed else None
    run.status = "completed" if all(item.status in {"completed", "skipped"} for item in run.steps) else "active"
    run.updated_at = datetime.now(timezone.utc)
    db.add(PatientAuditEvent(
        patient_id=run.patient_id,
        actor_user_id=user.id,
        action="care_pathway_step_completed" if completed else "care_pathway_step_reopened",
        summary="Care pathway step completed." if completed else "Care pathway step reopened.",
    ))
    db.commit()
    db.refresh(run)
    return run


def patient_pathway_status(db: Session, user: UserModel, patient_name: str):
    matches = list(db.scalars(
        select(PatientModel).where(
            _patient_scope(user),
            PatientModel.name.ilike(f"%{patient_name}%"),
        ).order_by(PatientModel.name, PatientModel.id).limit(3)
    ))
    if len(matches) > 1:
        raise HTTPException(409, "More than one patient matches that name. Add the patient's village or full name.")
    if not matches:
        raise HTTPException(404, "No matching patient in your records.")
    runs = list_pathways(db, user, matches[0].id)
    return {
        "answer": f"{len([run for run in runs if run.status == 'active'])} active care pathway(s) for {matches[0].name}.",
        "pathways": [
            {"id": run.id, "patient_id": run.patient_id, "patient": matches[0].name,
             "title": run.title, "status": run.status,
             "steps": [{"title": step.title, "status": step.status} for step in run.steps]}
            for run in runs
        ],
    }
