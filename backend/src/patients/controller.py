from fastapi import HTTPException
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.User.models import UserModel
from src.followups.models import FollowupModel
from src.patients.models import HbReading, PatientModel, PatientReferral, PatientReport, PatientScreening
from src.patients.Schema import AnemiaAssessment, PatientCreateSchema, ReferralCreate, ReferralUpdate, ScreeningSchema


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
    measurement = body.model_dump(exclude={"risk"})
    values = {**measurement, **({"risk": body.risk} if "risk" in body.model_fields_set else {})}
    statement = insert(PatientScreening).values(patient_id=patient_id, **values)
    screening = db.scalars(
        statement.on_conflict_do_update(index_elements=[PatientScreening.patient_id], set_=values)
        .returning(PatientScreening),
        execution_options={"populate_existing": True},
    ).one()
    if body.hb is not None:
        db.execute(
            insert(HbReading).values(patient_id=patient_id, **measurement)
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


def save_patient_report(db: Session, patient: PatientModel, filename: str, pdf: bytes) -> int:
    report = PatientReport(patient_id=patient.id, filename=filename, pdf=pdf)
    db.add(report)
    db.flush()
    report_id = report.id
    db.commit()
    return report_id


def record_anemia_assessment(db: Session, user: UserModel, patient_id: int, body: AnemiaAssessment):
    patient = get_patient(db, user, patient_id, lock=True)
    patient.anemia_status = body.status
    db.commit()
    return patient


def list_referrals(db: Session, user: UserModel, patient_id: int):
    get_patient(db, user, patient_id)
    query = select(PatientReferral).where(PatientReferral.patient_id == patient_id)
    return list(db.scalars(query.order_by(PatientReferral.referred_on.desc(), PatientReferral.id.desc())))


def create_referral(db: Session, user: UserModel, patient_id: int, body: ReferralCreate):
    get_patient(db, user, patient_id, lock=True)
    referral = PatientReferral(patient_id=patient_id, status="referred", **body.model_dump())
    db.add(referral)
    db.commit()
    db.refresh(referral)
    return referral


def update_referral(db: Session, user: UserModel, patient_id: int, referral_id: int, body: ReferralUpdate):
    get_patient(db, user, patient_id, lock=True)
    referral = db.scalar(select(PatientReferral).where(
        PatientReferral.id == referral_id, PatientReferral.patient_id == patient_id,
    ))
    if referral is None:
        raise HTTPException(404, "Referral not found")
    status_order = {"referred": 0, "attended": 1, "closed": 2}
    if status_order[body.status] < status_order[referral.status]:
        raise HTTPException(409, "Referral status cannot move backwards")
    referral.status = body.status
    referral.outcome = body.outcome
    db.commit()
    db.refresh(referral)
    return referral


def dashboard_summary(db: Session, user: UserModel):
    today = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    now = today.date()
    monday = now - timedelta(days=now.weekday())
    week_start = datetime.combine(monday, datetime.min.time(), tzinfo=today.tzinfo)
    assigned = select(PatientModel.id).where(patient_scope(user))
    registered = db.scalar(select(func.count()).select_from(PatientModel).where(
        patient_scope(user), PatientModel.registered_at >= week_start, PatientModel.registered_at <= today,
    ))
    # Compare each week's average across its recorded Hb measurements.
    readings = select(
        func.avg(HbReading.hb).filter(HbReading.date >= monday),
        func.avg(HbReading.hb).filter(HbReading.date < monday),
    ).where(
        HbReading.patient_id.in_(assigned),
        HbReading.date >= monday - timedelta(days=7),
        HbReading.date <= now,
    )
    current, previous = db.execute(readings).one()
    without_open_referral = db.scalar(select(func.count()).select_from(PatientScreening).where(
        PatientScreening.patient_id.in_(assigned),
        PatientScreening.risk == "high",
        ~select(PatientReferral.id).where(
            PatientReferral.patient_id == PatientScreening.patient_id,
            PatientReferral.status.in_(("referred", "attended")),
        ).exists(),
    ))
    return {
        "registered_this_week": registered,
        "weekly_hb_change": None if current is None or previous is None else round(current - previous, 1),
        "high_risk_without_open_referral": without_open_referral,
    }


def team_report(db: Session, user: UserModel, start: date | None, end: date | None,
                worker_id: int | None, village: str | None):
    workers = select(UserModel.id, UserModel.name).where(
        UserModel.admin_id == user.id, UserModel.role == "asha",
    )
    if worker_id is not None:
        workers = workers.where(UserModel.id == worker_id)
    rows = {
        identifier: dict(
            worker_id=identifier, worker_name=name, patients=0, hb_recorded=0, hb_pending=0,
            anemia_confirmed=0, not_assessed=0, followups_due=0, followups_overdue=0,
            followups_completed=0, referrals_referred=0, referrals_attended=0, referrals_closed=0,
        )
        for identifier, name in db.execute(workers.order_by(UserModel.name, UserModel.id))
    }
    if not rows:
        return []

    patients = select(PatientModel.id, PatientModel.asha_user_id, PatientModel.anemia_status).where(
        patient_scope(user), PatientModel.asha_user_id.in_(rows),
    )
    if village:
        patients = patients.where(PatientModel.village == village)
    cohort = patients.subquery()
    for _, owner, assessment in db.execute(select(cohort)):
        row = rows[owner]
        row["patients"] += 1
        row["anemia_confirmed"] += assessment == "confirmed"
        row["not_assessed"] += assessment is None

    def grouped(model, day, *metrics):
        query = select(cohort.c.asha_user_id, *metrics).join(model, model.patient_id == cohort.c.id)
        if start is not None:
            query = query.where(day >= start)
        if end is not None:
            query = query.where(day <= end)
        for owner, *counts in db.execute(query.group_by(cohort.c.asha_user_id)):
            rows[owner].update(zip((metric.name for metric in metrics), counts))

    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    grouped(HbReading, HbReading.date, func.count().label("hb_recorded"))
    grouped(PatientScreening, PatientScreening.date,
            func.count().filter(PatientScreening.hb.is_(None)).label("hb_pending"))
    grouped(FollowupModel, FollowupModel.due_date,
            func.count().filter(~FollowupModel.is_completed, FollowupModel.due_date == today).label("followups_due"),
            func.count().filter(~FollowupModel.is_completed, FollowupModel.due_date < today).label("followups_overdue"),
            func.count().filter(FollowupModel.is_completed).label("followups_completed"))
    grouped(PatientReferral, PatientReferral.referred_on,
            func.count().filter(PatientReferral.status == "referred").label("referrals_referred"),
            func.count().filter(PatientReferral.status == "attended").label("referrals_attended"),
            func.count().filter(PatientReferral.status == "closed").label("referrals_closed"))
    return list(rows.values())
