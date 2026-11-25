from fastapi import HTTPException
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.User.models import UserModel
from src.followups.models import FollowupModel
from src.patients.models import (AntenatalVisit, HbReading, IfaIntakeLog, IfaPlan, PatientAuditEvent,
                                 PatientModel, PatientReferral, PatientReport, PatientScreening, PregnancyEpisode)
from src.patients.Schema import (AntenatalVisitCreate, AnemiaAssessment, IfaIntakeInput, IfaPlanInput,
                                 PatientCreateSchema, PregnancyCreate, PregnancyStatusUpdate,
                                 ReferralCreate, ReferralUpdate, ScreeningSchema)
from src.pathways.service import start_referral_pathway, start_screening_pathway, sync_referral_pathway


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


def log_patient_action(db: Session, user: UserModel, patient_id: int, action: str, summary: str) -> None:
    db.add(PatientAuditEvent(
        patient_id=patient_id, actor_user_id=user.id, action=action, summary=summary,
    ))


def list_patient_activity(db: Session, user: UserModel, patient_id: int):
    get_patient(db, user, patient_id)
    query = (
        select(
            PatientAuditEvent.id, UserModel.name.label("actor_name"), PatientAuditEvent.action,
            PatientAuditEvent.summary, PatientAuditEvent.created_at,
        )
        .join(PatientModel, PatientModel.id == PatientAuditEvent.patient_id)
        .outerjoin(UserModel, UserModel.id == PatientAuditEvent.actor_user_id)
        .where(PatientAuditEvent.patient_id == patient_id, patient_scope(user))
        .order_by(PatientAuditEvent.created_at.desc(), PatientAuditEvent.id.desc())
    )
    return [dict(row) for row in db.execute(query).mappings()]


def create_patient(db: Session, user: UserModel, body: PatientCreateSchema) -> PatientModel:
    conditions = [
        PatientModel.asha_user_id == user.id,
        func.lower(func.trim(PatientModel.name)) == body.name.casefold(),
    ]
    if body.village:
        conditions.append(func.lower(func.trim(PatientModel.village)) == body.village.casefold())
    if body.age is not None:
        conditions.append(PatientModel.age == body.age)
    matches = list(db.scalars(
        select(PatientModel).where(*conditions).order_by(PatientModel.name, PatientModel.id).limit(6)
    ))
    if matches and not body.confirm_possible_duplicate:
        raise HTTPException(409, {
            "code": "possible_duplicate",
            "message": "A patient with matching details already exists. Review the matches before continuing.",
            "matches": [{"id": row.id, "name": row.name, "village": row.village, "age": row.age} for row in matches],
        })
    patient = PatientModel(
        asha_user_id=user.id,
        **body.model_dump(exclude={"confirm_possible_duplicate"}),
        consent_recorded_at=datetime.now(timezone.utc),
        consent_recorded_by=user.id,
    )
    db.add(patient)
    db.flush()
    log_patient_action(db, user, patient.id, "patient_registered", "Patient record created; consent confirmed by ASHA.")
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
    pathway = start_screening_pathway(db, user, patient_id, screening)
    log_patient_action(db, user, patient_id, "hb_screening_saved", "Hb screening saved." if body.hb is not None else "Hb screening marked pending.")
    if pathway is not None:
        log_patient_action(db, user, patient_id, "care_pathway_started", "Hb result follow-up pathway started.")
    db.commit()
    return screening


def list_hb_readings(db: Session, user: UserModel, patient_id: int) -> list[HbReading]:
    get_patient(db, user, patient_id)
    return list(db.scalars(
        select(HbReading).where(HbReading.patient_id == patient_id)
        .order_by(HbReading.date.desc(), HbReading.id.desc())
    ))


def save_patient_report(db: Session, user: UserModel, patient: PatientModel, filename: str, pdf: bytes) -> int:
    report = PatientReport(patient_id=patient.id, filename=filename, pdf=pdf)
    db.add(report)
    db.flush()
    report_id = report.id
    log_patient_action(db, user, patient.id, "patient_report_uploaded", "Patient report uploaded.")
    db.commit()
    return report_id


def record_anemia_assessment(db: Session, user: UserModel, patient_id: int, body: AnemiaAssessment):
    patient = get_patient(db, user, patient_id, lock=True)
    patient.anemia_status = body.status
    log_patient_action(db, user, patient_id, "anemia_assessment_updated", "Anemia assessment updated.")
    db.commit()
    return patient


def record_consent(db: Session, user: UserModel, patient_id: int, consent_obtained: bool):
    patient = get_patient(db, user, patient_id, lock=True)
    patient.consent_obtained = consent_obtained
    patient.consent_recorded_at = datetime.now(timezone.utc)
    patient.consent_recorded_by = user.id
    summary = "Patient consent confirmed by ASHA." if consent_obtained else "Consent withdrawal recorded by ASHA."
    log_patient_action(db, user, patient_id, "consent_updated", summary)
    db.commit()
    db.refresh(patient)
    return patient


def _owned_pregnancy(db: Session, user: UserModel, patient_id: int, pregnancy_id: int, *, lock: bool = False):
    get_patient(db, user, patient_id, lock=lock)
    query = select(PregnancyEpisode).where(
        PregnancyEpisode.id == pregnancy_id, PregnancyEpisode.patient_id == patient_id,
    )
    episode = db.scalar(query.with_for_update() if lock else query)
    if episode is None:
        raise HTTPException(404, "Pregnancy record not found")
    return episode


def pregnancy_care(db: Session, user: UserModel, patient_id: int):
    get_patient(db, user, patient_id)
    episode = db.scalar(select(PregnancyEpisode).where(
        PregnancyEpisode.patient_id == patient_id, PregnancyEpisode.status == "active",
    ))
    if episode is None:
        return {"pregnancy": None, "visits": [], "ifa_plan": None, "ifa_logs": []}
    visits = list(db.scalars(select(AntenatalVisit).where(
        AntenatalVisit.pregnancy_id == episode.id,
    ).order_by(AntenatalVisit.due_date, AntenatalVisit.id)))
    plan = db.scalar(select(IfaPlan).where(IfaPlan.pregnancy_id == episode.id))
    logs = list(db.scalars(select(IfaIntakeLog).where(
        IfaIntakeLog.pregnancy_id == episode.id,
    ).order_by(IfaIntakeLog.intake_date.desc(), IfaIntakeLog.id.desc()).limit(90)))
    return {"pregnancy": episode, "visits": visits, "ifa_plan": plan, "ifa_logs": logs}


def create_pregnancy(db: Session, user: UserModel, patient_id: int, body: PregnancyCreate):
    patient = get_patient(db, user, patient_id, lock=True)
    if patient.consent_obtained is not True:
        raise HTTPException(409, "Confirm current patient consent before recording pregnancy care.")
    existing = db.scalar(select(PregnancyEpisode.id).where(
        PregnancyEpisode.patient_id == patient_id, PregnancyEpisode.status == "active",
    ))
    if existing is not None:
        raise HTTPException(409, "An active pregnancy is already recorded for this patient.")
    episode = PregnancyEpisode(patient_id=patient_id, recorded_by_user_id=user.id, **body.model_dump())
    db.add(episode)
    db.flush()
    log_patient_action(db, user, patient_id, "pregnancy_recorded", "Pregnancy dates recorded from the patient's care record.")
    db.commit()
    db.refresh(episode)
    return episode


def update_pregnancy_status(db: Session, user: UserModel, patient_id: int, pregnancy_id: int, body: PregnancyStatusUpdate):
    episode = _owned_pregnancy(db, user, patient_id, pregnancy_id, lock=True)
    if episode.status != "active":
        raise HTTPException(409, "This pregnancy record is already closed.")
    episode.status = body.status
    if body.status in {"completed", "closed"}:
        planned_visits = list(db.scalars(select(AntenatalVisit).where(
            AntenatalVisit.pregnancy_id == pregnancy_id, AntenatalVisit.status == "planned",
        ).with_for_update()))
        for visit in planned_visits:
            visit.status = "cancelled"
            if visit.followup_id is not None:
                followup = db.get(FollowupModel, visit.followup_id)
                if followup is not None:
                    followup.is_archived = True
    log_patient_action(db, user, patient_id, "pregnancy_closed", "Pregnancy care episode marked " + body.status + ".")
    db.commit()
    db.refresh(episode)
    return episode


def schedule_anc_visit(db: Session, user: UserModel, patient_id: int, pregnancy_id: int, body: AntenatalVisitCreate):
    episode = _owned_pregnancy(db, user, patient_id, pregnancy_id, lock=True)
    if episode.status != "active":
        raise HTTPException(409, "ANC visits can only be scheduled for an active pregnancy.")
    if body.due_date < datetime.now(timezone(timedelta(hours=5, minutes=30))).date():
        raise HTTPException(422, "For a past ANC date, record the visit as completed instead of scheduling it.")
    visit = AntenatalVisit(pregnancy_id=pregnancy_id, recorded_by_user_id=user.id, **body.model_dump())
    db.add(visit)
    db.flush()
    followup = FollowupModel(
        patient_id=patient_id, title=f"ANC visit {visit.id}", due_date=visit.due_date,
    )
    db.add(followup)
    db.flush()
    visit.followup_id = followup.id
    log_patient_action(db, user, patient_id, "anc_visit_scheduled", "ANC visit scheduled from the recorded care plan.")
    db.commit()
    db.refresh(visit)
    return visit


def update_anc_visit(db: Session, user: UserModel, patient_id: int, pregnancy_id: int, visit_id: int, status: str):
    _owned_pregnancy(db, user, patient_id, pregnancy_id, lock=True)
    visit = db.scalar(select(AntenatalVisit).where(
        AntenatalVisit.id == visit_id, AntenatalVisit.pregnancy_id == pregnancy_id,
    ).with_for_update())
    if visit is None:
        raise HTTPException(404, "ANC visit not found")
    if visit.status != "planned":
        raise HTTPException(409, "Only a planned ANC visit can be completed or cancelled.")
    if status == "completed" and visit.due_date > datetime.now(timezone(timedelta(hours=5, minutes=30))).date():
        raise HTTPException(422, "A future ANC visit cannot be marked completed.")
    visit.status = status
    if status == "completed":
        visit.completed_at = datetime.now(timezone.utc)
    if visit.followup_id is not None:
        followup = db.get(FollowupModel, visit.followup_id)
        if followup is not None:
            followup.is_completed = status == "completed"
            followup.is_archived = status == "cancelled"
    log_patient_action(db, user, patient_id, "anc_visit_" + status, "ANC visit marked " + status + ".")
    db.commit()
    db.refresh(visit)
    return visit


def save_ifa_plan(db: Session, user: UserModel, patient_id: int, pregnancy_id: int, body: IfaPlanInput):
    episode = _owned_pregnancy(db, user, patient_id, pregnancy_id, lock=True)
    if episode.status != "active":
        raise HTTPException(409, "IFA instructions can only be updated for an active pregnancy.")
    plan = db.scalar(select(IfaPlan).where(IfaPlan.pregnancy_id == pregnancy_id).with_for_update())
    if plan is None:
        plan = IfaPlan(pregnancy_id=pregnancy_id, recorded_by_user_id=user.id, **body.model_dump())
        db.add(plan)
    else:
        for field, value in body.model_dump().items():
            setattr(plan, field, value)
        plan.recorded_by_user_id = user.id
        plan.updated_at = datetime.now(timezone.utc)
    log_patient_action(db, user, patient_id, "ifa_plan_recorded", "IFA instructions recorded from an authorized care plan.")
    db.commit()
    db.refresh(plan)
    return plan


def record_ifa_intake(db: Session, user: UserModel, patient_id: int, pregnancy_id: int, body: IfaIntakeInput):
    episode = _owned_pregnancy(db, user, patient_id, pregnancy_id, lock=True)
    if episode.status != "active":
        raise HTTPException(409, "IFA intake can only be recorded for an active pregnancy.")
    plan = db.scalar(select(IfaPlan).where(IfaPlan.pregnancy_id == pregnancy_id))
    if plan is None:
        raise HTTPException(409, "Record the provider's IFA instructions before tracking intake.")
    if body.intake_date < plan.start_date:
        raise HTTPException(422, "Intake date cannot be earlier than the recorded IFA plan start date.")
    log = db.scalar(select(IfaIntakeLog).where(
        IfaIntakeLog.pregnancy_id == pregnancy_id, IfaIntakeLog.intake_date == body.intake_date,
    ).with_for_update())
    if log is None:
        log = IfaIntakeLog(pregnancy_id=pregnancy_id, recorded_by_user_id=user.id, **body.model_dump())
        db.add(log)
    else:
        log.status = body.status
        log.recorded_by_user_id = user.id
    log_patient_action(db, user, patient_id, "ifa_intake_recorded", "IFA intake status recorded as " + body.status + ".")
    db.commit()
    db.refresh(log)
    return log


def list_referrals(db: Session, user: UserModel, patient_id: int):
    get_patient(db, user, patient_id)
    query = select(PatientReferral).where(PatientReferral.patient_id == patient_id)
    return list(db.scalars(query.order_by(PatientReferral.referred_on.desc(), PatientReferral.id.desc())))


def create_referral(db: Session, user: UserModel, patient_id: int, body: ReferralCreate):
    get_patient(db, user, patient_id, lock=True)
    referral = PatientReferral(patient_id=patient_id, status="referred", **body.model_dump())
    db.add(referral)
    db.flush()
    start_referral_pathway(db, user, referral)
    log_patient_action(db, user, patient_id, "care_pathway_started", "Referral follow-up pathway started.")
    log_patient_action(db, user, patient_id, "referral_created", "Referral created for " + body.facility + ".")
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
    sync_referral_pathway(db, user, referral)
    summary = "Referral marked attended." if body.status == "attended" else "Referral outcome recorded." if body.status == "closed" else "Referral updated."
    log_patient_action(db, user, patient_id, "referral_updated", summary)
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
            func.count().filter(~FollowupModel.is_archived, ~FollowupModel.is_completed, FollowupModel.due_date == today).label("followups_due"),
            func.count().filter(~FollowupModel.is_archived, ~FollowupModel.is_completed, FollowupModel.due_date < today).label("followups_overdue"),
            func.count().filter(~FollowupModel.is_archived, FollowupModel.is_completed).label("followups_completed"))
    grouped(PatientReferral, PatientReferral.referred_on,
            func.count().filter(PatientReferral.status == "referred").label("referrals_referred"),
            func.count().filter(PatientReferral.status == "attended").label("referrals_attended"),
            func.count().filter(PatientReferral.status == "closed").label("referrals_closed"))
    return list(rows.values())
