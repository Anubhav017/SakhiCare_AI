from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.followups.models import FollowupModel
from src.followups.Schema import FollowupCreateSchema
from src.patients.controller import get_patient, log_patient_action, patient_scope
from src.patients.models import PatientModel
from src.User.models import UserModel


def list_followups(db: Session, user: UserModel) -> list[FollowupModel]:
    query = (
        select(FollowupModel)
        .join(PatientModel, FollowupModel.patient_id == PatientModel.id)
        .where(patient_scope(user), FollowupModel.is_archived.is_(False))
        .order_by(FollowupModel.due_date, FollowupModel.id)
    )
    return list(db.scalars(query))


def create_followup(db: Session, user: UserModel, body: FollowupCreateSchema) -> FollowupModel:
    get_patient(db, user, body.patient_id, lock=True)
    followup = FollowupModel(**body.model_dump())
    db.add(followup)
    db.flush()
    log_patient_action(db, user, body.patient_id, "followup_scheduled", "Follow-up scheduled: " + body.title + ".")
    db.commit()
    db.refresh(followup)
    return followup


def update_followup(db: Session, user: UserModel, followup_id: int, completed: bool) -> FollowupModel:
    owned_patients = select(PatientModel.id).where(patient_scope(user))
    followup = db.scalar(
        update(FollowupModel)
        .where(FollowupModel.id == followup_id, FollowupModel.patient_id.in_(owned_patients),
               FollowupModel.is_archived.is_(False))
        .values(is_completed=completed)
        .returning(FollowupModel)
    )
    if followup is None:
        raise HTTPException(404, "Follow-up not found")
    log_patient_action(
        db, user, followup.patient_id,
        "followup_completed" if completed else "followup_reopened",
        "Follow-up marked complete." if completed else "Follow-up reopened.",
    )
    db.commit()
    return followup
