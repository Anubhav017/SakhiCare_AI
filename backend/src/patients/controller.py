from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.User.models import UserModel
from src.patients.models import HbReading, PatientModel, PatientScreening
from src.patients.Schema import PatientCreateSchema, ScreeningSchema


def patient_scope(user: UserModel):
    if user.role == "super_admin":
        scope = select(UserModel.id).where(UserModel.role == "asha", UserModel.admin_id == user.id)
        return PatientModel.asha_user_id.in_(scope)
    return PatientModel.asha_user_id == user.id


def list_patients(db: Session, user: UserModel) -> list[PatientModel]:
    query = select(PatientModel).where(patient_scope(user)).order_by(PatientModel.name, PatientModel.id)
    return list(db.scalars(query))


def get_patient(db: Session, user: UserModel, patient_id: int, *, lock: bool = False) -> PatientModel:
    query = select(PatientModel).where(PatientModel.id == patient_id, patient_scope(user))
    patient = db.scalar(query.with_for_update() if lock else query)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    return patient


def create_patient(db: Session, asha_user_id: int, body: PatientCreateSchema) -> PatientModel:
    patient = PatientModel(asha_user_id=asha_user_id, **body.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def save_screening(db: Session, user: UserModel, patient_id: int, body: ScreeningSchema) -> PatientScreening:
    get_patient(db, user, patient_id, lock=True)
    values = body.model_dump()
    statement = insert(PatientScreening).values(patient_id=patient_id, **values)
    screening = db.scalars(
        statement.on_conflict_do_update(index_elements=[PatientScreening.patient_id], set_=values)
        .returning(PatientScreening),
        execution_options={"populate_existing": True},
    ).one()
    if body.hb is not None:
        db.execute(
            insert(HbReading).values(patient_id=patient_id, **values)
            .on_conflict_do_nothing(constraint="uq_patient_hb_reading")
        )
    db.commit()
    return screening


def list_hb_readings(db: Session, user: UserModel, patient_id: int) -> list[HbReading]:
    get_patient(db, user, patient_id)
    return list(db.scalars(
        select(HbReading).where(HbReading.patient_id == patient_id)
        .order_by(HbReading.date.desc(), HbReading.id.desc())
    ))
