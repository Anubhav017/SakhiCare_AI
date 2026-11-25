"""Idempotently add synthetic UI and workflow data to a local SakhiCare DB."""

from datetime import date, datetime, timedelta, timezone
import os

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.User.models import UserModel
from src.followups.models import FollowupModel
from src.patients.models import HbReading, PatientAuditEvent, PatientModel, PatientReferral, PatientScreening
from src.pathways.models import CarePathwayRun
from src.pathways.service import start_referral_pathway, start_screening_pathway, sync_referral_pathway
from src.utils.config import settings

TEST_PREFIX = "[TEST]"
ASHA_USERNAME = "asha_demo_sunita"
INDIA_TZ = timezone(timedelta(hours=5, minutes=30))

FIXTURES = [
    ("Demo 01 · High risk · open referral", "Test Village North", 24, 7.8, "high", "confirmed"),
    ("Demo 02 · Moderate risk · attended", "Test Village East", 31, 9.2, "moderate", "confirmed"),
    ("Demo 03 · Moderate risk · no referral", "Test Village West", 19, 10.1, "moderate", None),
    ("Demo 04 · Low risk", "Test Village South", 27, 11.4, "low", "not_anemic"),
    ("Demo 05 · Hb screening pending", "Test Village Central", 22, None, None, None),
    ("Demo 06 · Referral closed", "Test Village North", 36, 8.6, "high", "confirmed"),
    ("Demo 07 · High risk", "Test Village East", 29, 8.1, "high", "confirmed"),
    ("Demo 08 · Low risk", "Test Village West", 25, 11.8, "low", "not_anemic"),
    ("Demo 09 · Moderate risk", "Test Village South", 33, 9.8, "moderate", "confirmed"),
    ("Demo 10 · Screening pending", "Test Village Central", 20, None, None, None),
    ("Demo 11 · High risk · no referral", "Test Village North", 40, 7.5, "high", "confirmed"),
    ("Demo 12 · Moderate risk", "Test Village East", 26, 10.0, "moderate", None),
]


def _today() -> date:
    return datetime.now(INDIA_TZ).date()


def main() -> None:
    db_url = make_url(settings.DB_CONNECTION)
    local_host = db_url.host in {"localhost", "127.0.0.1", "::1"}
    compose_host = db_url.host == "postgres" and os.environ.get("ALLOW_SYNTHETIC_DATA") == "1"
    if db_url.database != "sakhicare" or not (local_host or compose_host):
        raise SystemExit(
            "Refusing to seed. Use the local 'sakhicare' database; Docker Compose requires "
            "ALLOW_SYNTHETIC_DATA=1 explicitly."
        )

    today = _today()
    engine = create_engine(settings.DB_CONNECTION)
    try:
        with Session(engine) as db:
            asha = db.scalar(select(UserModel).where(UserModel.username == ASHA_USERNAME))
            if asha is None or asha.role != "asha":
                raise SystemExit(f"Create the ASHA account '{ASHA_USERNAME}' before seeding synthetic patients.")

            patients: list[PatientModel] = []
            for index, (label, village, age, hb, risk, anemia) in enumerate(FIXTURES):
                name = f"{TEST_PREFIX} {label}"
                patient = db.scalar(select(PatientModel).where(
                    PatientModel.asha_user_id == asha.id, PatientModel.name == name,
                ))
                if patient is None:
                    patient = PatientModel(
                        asha_user_id=asha.id, consent_obtained=True,
                        consent_recorded_at=datetime.now(timezone.utc), consent_recorded_by=asha.id,
                        anemia_status=anemia, name=name, village=village, age=age,
                    )
                    db.add(patient)
                    db.flush()
                    db.add(PatientAuditEvent(
                        patient_id=patient.id, actor_user_id=asha.id, action="test_data_seeded",
                        summary="Synthetic test patient created for UI and workflow checks.",
                    ))
                patients.append(patient)

                screening = db.get(PatientScreening, patient.id)
                screening_date = today - timedelta(days=(index + 1) * 3)
                if screening is None:
                    screening = PatientScreening(
                        patient_id=patient.id, date=screening_date, hb=hb,
                        method="Digital hemoglobinometer" if hb is not None else "", risk=risk,
                    )
                    db.add(screening)
                    db.flush()
                if hb is not None and db.scalar(select(HbReading.id).where(
                    HbReading.patient_id == patient.id, HbReading.date == screening.date, HbReading.hb == hb,
                )) is None:
                    db.add(HbReading(
                        patient_id=patient.id, date=screening.date, hb=hb,
                        method="Digital hemoglobinometer",
                    ))
                start_screening_pathway(db, asha, patient.id, screening)

                followup_title = "Review care plan" if index % 2 == 0 else "Check next contact"
                due_date = today + timedelta(days=(-3, 0, 7, -5, 2, -1, 1, 5, -2, 3, 0, 8)[index])
                if db.scalar(select(FollowupModel.id).where(
                    FollowupModel.patient_id == patient.id,
                    FollowupModel.title == followup_title,
                    FollowupModel.due_date == due_date,
                )) is None:
                    db.add(FollowupModel(
                        patient_id=patient.id, title=followup_title, due_date=due_date,
                        is_completed=index in {3, 7},
                    ))

            referral_fixtures = [
                (0, "Primary Health Centre - Test", "referred", None),
                (1, "Community Health Centre - Test", "attended", None),
                (5, "District Hospital - Test", "closed", "Synthetic demo outcome recorded."),
                (6, "Primary Health Centre - Test", "referred", None),
                (8, "Community Health Centre - Test", "attended", None),
            ]
            referrals: list[PatientReferral] = []
            for patient_index, facility, status, outcome in referral_fixtures:
                patient = patients[patient_index]
                referred_on = today - timedelta(days=2 + patient_index)
                referral = db.scalar(select(PatientReferral).where(
                    PatientReferral.patient_id == patient.id,
                    PatientReferral.facility == facility,
                ))
                if referral is None:
                    referral = PatientReferral(
                        patient_id=patient.id, facility=facility, referred_on=referred_on,
                        status=status, outcome=outcome,
                    )
                    db.add(referral)
                    db.flush()
                referrals.append(referral)
                run = start_referral_pathway(db, asha, referral)
                if referral.status in {"attended", "closed"}:
                    sync_referral_pathway(db, asha, referral)
                elif run is not None and run.steps:
                    run.steps[0].status = "completed"
                    run.steps[0].completed_at = datetime.now(timezone.utc)
                    run.steps[0].completed_by_user_id = asha.id

            # Keep one Hb follow-up partly complete to show a resumable pathway.
            for patient_index in (0, 2):
                patient = patients[patient_index]
                screening = db.get(PatientScreening, patient.id)
                if screening is None:
                    continue
                run_key = f"screening:{patient.id}:{screening.date.isoformat()}:{screening.hb}:{screening.risk}"
                run = db.scalar(select(CarePathwayRun).where(CarePathwayRun.source_key == run_key))
                if run is not None and run.steps:
                    step = run.steps[0]
                    step.status = "completed"
                    step.completed_at = step.completed_at or datetime.now(timezone.utc)
                    step.completed_by_user_id = step.completed_by_user_id or asha.id

            db.commit()
            print(f"Synthetic demo data ready: {len(patients)} patients, Hb history, follow-ups, referrals, and care pathways.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
