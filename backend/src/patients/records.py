from datetime import datetime, timedelta, timezone
import re
from typing import Literal

from fastapi import HTTPException
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.followups.models import FollowupModel
from src.patients.controller import patient_scope
from src.patients.models import (AntenatalVisit, IfaIntakeLog, PatientModel, PatientReferral,
                                 PatientScreening, PregnancyEpisode)
from src.pathways.models import CarePathwayRun, CarePathwayStep
from src.User.models import UserModel
from src.User.roles import is_supervisor, managed_user_ids
from src.utils.ai_client import call_tool


class RecordQueryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "patients", "patient_count", "due_followups", "followups_completed", "followups_upcoming",
        "referrals_open", "referrals_attended", "referrals_closed", "pathway_status", "worker_patients", "unknown",
        "active_pregnancies", "anc_visits_planned", "ifa_intake_missed",
    ]
    patient_name: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=100)
    worker_name: str | None = Field(default=None, max_length=180)
    risk: Literal["low", "moderate", "high"] | None = None
    anemia_status: Literal["confirmed", "not_anemic", "not_assessed"] | None = None
    screening_status: Literal["recorded", "pending"] | None = None


def _query_records_tool(intent: str, patient_name: str | None = None, village: str | None = None,
                       worker_name: str | None = None, risk: str | None = None,
                       anemia_status: str | None = None, screening_status: str | None = None) -> str:
    """Plan a read-only query against approved SakhiCare records. Never writes data."""
    return "Query plan accepted for server-side validation."


record_query_tool = StructuredTool.from_function(
    func=_query_records_tool,
    name="query_sakhicare_records",
    description=(
        "Select a read-only query from the user's permitted SakhiCare records. "
        "Choose only supported filters; never request SQL or make changes. "
        "Use patient_name or village only when the question names one."
    ),
    args_schema=RecordQueryArgs,
)


def _record_intent(question: str, is_admin: bool) -> str | None:
    q = " ".join(question.casefold().replace("-", " ").replace("?", " ").replace("!", " ").split())
    if q in {"patient_count", "patients_by_worker", "worker_patients", "due_followups"}:
        return q
    if any(token in q for token in ("care pathway", "care pathways", "pathway status", "pathways", "runbook")):
        return "pathway_status"
    if "ifa" in q and any(token in q for token in ("missed", "not taken", "forgot")):
        return "ifa_intake_missed"
    if any(token in q for token in ("anc", "antenatal")) and any(token in q for token in ("due", "upcoming", "scheduled", "pending")):
        return "anc_visits_planned"
    if any(token in q for token in ("pregnant", "pregnancy", "edd")):
        return "active_pregnancies"
    if "high risk" in q:
        return "high_risk_patients"
    if "moderate risk" in q:
        return "moderate_risk_patients"
    if "low risk" in q:
        return "low_risk_patients"
    if any(token in q for token in ("anemia", "anaemia", "anemic", "anaemic")):
        if any(token in q for token in ("not assessed", "unassessed", "pending")):
            return "anemia_not_assessed"
        if any(token in q for token in ("no anemia", "not anemic", "not anaemic")):
            return "anemia_not_confirmed"
        return "anemia_confirmed"
    if any(token in q for token in ("screening pending", "hb pending", "not screened", "unscreened")):
        return "screening_pending"
    if any(token in q for token in ("screened", "hb test", "hemoglobin", "haemoglobin")):
        return "screening_recorded"
    if any(token in q for token in ("referral", "referred")):
        if any(token in q for token in ("closed", "outcome")):
            return "referrals_closed"
        if any(token in q for token in ("attended", "visited")):
            return "referrals_attended"
        return "referrals_open"
    if any(token in q for token in ("follow up", "followup", "follow ups")):
        if any(token in q for token in ("complete", "done")):
            return "followups_completed"
        if any(token in q for token in ("upcoming", "future")):
            return "followups_upcoming"
        return "due_followups"
    asks_patient_count = (
        any(token in q for token in ("patient count", "total patients", "patient total"))
        or re.search(r"\bhow many\s+(?:total\s+)?patients?\b", q) is not None
        or re.search(r"\bnumber of\s+(?:total\s+)?patients?\b", q) is not None
    )
    if asks_patient_count:
        if is_admin and any(token in q for token in ("each asha", "by asha", "per asha")):
            return "patients_by_worker"
        return "patient_count"
    return None


def _patient_name_search(question: str) -> str | None:
    question = " ".join(question.strip().split())
    patterns = (
        r"^(?:show|find|search|lookup)(?: me)?(?: the)? patient(?: details)?(?: for)?\s+(.+)$",
        r"^patient details for\s+(.+)$",
        r"^(.+?)\s+patient list$",
    )
    for pattern in patterns:
        match = re.match(pattern, question, flags=re.IGNORECASE)
        if match:
            name = match.group(1).strip(" .?!'’\"")
            return name or None
    return None


def _pathway_patient_search(question: str) -> str | None:
    question = " ".join(question.strip().split())
    patterns = (
        r"^(?:what is|show|check|tell me)?\s*(?:the )?(?:care )?pathway(?: status)?\s+(?:for|of)\s+(.+)$",
        r"^(?:show|check|tell me)\s+(.+?)['’]s\s+(?:care )?pathways?(?: status)?$",
        r"^status of (?:the )?(?:care )?pathways? for\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, question, flags=re.IGNORECASE)
        if match:
            patient = match.group(1).strip(" .?!'’\"")
            return patient or None
    return None


def _patient_result(db: Session, user: UserModel, predicate, label: str):
    query = (
        select(PatientModel.id, PatientModel.name, PatientModel.village, PatientModel.age,
               PatientModel.anemia_status, PatientScreening.risk)
        .outerjoin(PatientScreening, PatientScreening.patient_id == PatientModel.id)
        .where(patient_scope(user), predicate)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(PatientModel.name, PatientModel.id).limit(50))
    return {
        "answer": f"Found {total} {label}.", "total": total,
        "patients": [dict(row) for row in rows.mappings()], "truncated": total > 50,
    }


def _read_dynamic_records(db: Session, user: UserModel, intent: str, patient_name: str | None = None):
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    if intent == "patient_count":
        count = db.scalar(select(func.count()).select_from(PatientModel).where(patient_scope(user))) or 0
        return {"answer": f"You have {count} patients.", "count": count}
    if intent == "active_pregnancies":
        query = (
            select(PregnancyEpisode.id, PatientModel.id.label("patient_id"), PatientModel.name,
                   PatientModel.village, PregnancyEpisode.lmp_date, PregnancyEpisode.edd_date)
            .join(PatientModel, PatientModel.id == PregnancyEpisode.patient_id)
            .where(patient_scope(user), PregnancyEpisode.status == "active")
        )
        if patient_name:
            query = query.where(func.lower(PatientModel.name).contains(patient_name.casefold(), autoescape=True))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(PregnancyEpisode.edd_date, PregnancyEpisode.id).limit(50))
        return {"answer": f"Found {total} active pregnancy record(s).", "total": total,
                "pregnancies": [dict(row) for row in rows.mappings()], "truncated": total > 50}
    if intent == "anc_visits_planned":
        query = (
            select(AntenatalVisit.id, PatientModel.id.label("patient_id"), PatientModel.name.label("patient"),
                   AntenatalVisit.due_date, AntenatalVisit.facility, AntenatalVisit.status)
            .join(PregnancyEpisode, PregnancyEpisode.id == AntenatalVisit.pregnancy_id)
            .join(PatientModel, PatientModel.id == PregnancyEpisode.patient_id)
            .where(patient_scope(user), PregnancyEpisode.status == "active", AntenatalVisit.status == "planned")
        )
        if patient_name:
            query = query.where(func.lower(PatientModel.name).contains(patient_name.casefold(), autoescape=True))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(AntenatalVisit.due_date, AntenatalVisit.id).limit(50))
        return {"answer": f"Found {total} planned ANC visit(s).", "total": total,
                "anc_visits": [dict(row) for row in rows.mappings()], "truncated": total > 50}
    if intent == "ifa_intake_missed":
        query = (
            select(IfaIntakeLog.id, PatientModel.id.label("patient_id"), PatientModel.name.label("patient"),
                   IfaIntakeLog.intake_date, IfaIntakeLog.status)
            .join(PregnancyEpisode, PregnancyEpisode.id == IfaIntakeLog.pregnancy_id)
            .join(PatientModel, PatientModel.id == PregnancyEpisode.patient_id)
            .where(patient_scope(user), IfaIntakeLog.status == "missed")
        )
        if patient_name:
            query = query.where(func.lower(PatientModel.name).contains(patient_name.casefold(), autoescape=True))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(IfaIntakeLog.intake_date.desc(), IfaIntakeLog.id.desc()).limit(50))
        return {"answer": f"Found {total} explicitly reported missed IFA intake record(s).", "total": total,
                "ifa_intake_logs": [dict(row) for row in rows.mappings()], "truncated": total > 50}
    predicates = {
        "high_risk_patients": (PatientScreening.risk == "high", "high-risk patients"),
        "moderate_risk_patients": (PatientScreening.risk == "moderate", "moderate-risk patients"),
        "low_risk_patients": (PatientScreening.risk == "low", "low-risk patients"),
        "anemia_confirmed": (PatientModel.anemia_status == "confirmed", "patients with confirmed anemia"),
        "anemia_not_confirmed": (PatientModel.anemia_status == "not_anemic", "patients recorded as not anemic"),
        "anemia_not_assessed": (PatientModel.anemia_status.is_(None), "patients with no anemia assessment"),
        "screening_pending": ((PatientScreening.patient_id.is_(None) | PatientScreening.hb.is_(None)), "patients with Hb screening pending"),
        "screening_recorded": ((PatientScreening.patient_id.is_not(None) & PatientScreening.hb.is_not(None)), "patients with an Hb result"),
    }
    if intent in predicates:
        predicate, label = predicates[intent]
        return _patient_result(db, user, predicate, label)
    if intent in ("due_followups", "followups_completed", "followups_upcoming"):
        query = select(
            FollowupModel.id, FollowupModel.patient_id, PatientModel.name.label("patient"),
            FollowupModel.title, FollowupModel.due_date, FollowupModel.is_completed,
        ).join(PatientModel, PatientModel.id == FollowupModel.patient_id).where(
            patient_scope(user), FollowupModel.is_archived.is_(False),
        )
        if intent == "due_followups":
            query = query.where(FollowupModel.is_completed.is_(False), FollowupModel.due_date <= today)
            label = "due or overdue follow-ups"
        elif intent == "followups_completed":
            query = query.where(FollowupModel.is_completed.is_(True))
            label = "completed follow-ups"
        else:
            query = query.where(FollowupModel.is_completed.is_(False), FollowupModel.due_date > today)
            label = "upcoming follow-ups"
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(FollowupModel.due_date, FollowupModel.id).limit(50))
        return {"answer": f"Found {total} {label}.", "total": total,
                "followups": [dict(row) for row in rows.mappings()], "truncated": total > 50}
    if intent in ("referrals_open", "referrals_attended", "referrals_closed"):
        query = select(
            PatientReferral.id, PatientReferral.patient_id, PatientModel.name.label("patient"),
            PatientReferral.facility, PatientReferral.referred_on, PatientReferral.status, PatientReferral.outcome,
        ).join(PatientModel, PatientModel.id == PatientReferral.patient_id).where(patient_scope(user))
        statuses = ("referred", "attended") if intent == "referrals_open" else (intent.removeprefix("referrals_"),)
        query = query.where(PatientReferral.status.in_(statuses))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(PatientReferral.referred_on.desc(), PatientReferral.id.desc()).limit(50))
        return {"answer": f"Found {total} {intent.replace('_', ' ')}.", "total": total,
                "referrals": [dict(row) for row in rows.mappings()], "truncated": total > 50}
    if intent == "pathway_status":
        query = (
            select(CarePathwayRun)
            .join(PatientModel, PatientModel.id == CarePathwayRun.patient_id)
            .options(selectinload(CarePathwayRun.steps))
            .where(patient_scope(user), CarePathwayRun.status.in_(("active", "completed")))
            .order_by(CarePathwayRun.updated_at.desc(), CarePathwayRun.id.desc())
        )
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        runs = list(db.scalars(query.limit(50)))
        names = dict(db.execute(select(PatientModel.id, PatientModel.name).where(
            PatientModel.id.in_([run.patient_id for run in runs])
        )).all()) if runs else {}
        return {"answer": f"Found {total} care pathways.", "total": total,
                "pathways": [{
                    "id": run.id, "patient_id": run.patient_id, "patient": names.get(run.patient_id, "Patient"),
                    "title": run.title, "status": run.status,
                    "steps": [{"title": step.title, "status": step.status} for step in run.steps],
                } for run in runs], "truncated": total > 50}
    return None


def _read_planned_records(db: Session, user: UserModel, plan: RecordQueryArgs):
    if plan.intent == "unknown":
        return None
    if plan.intent == "worker_patients":
        return read_records(db, user, "worker_patients", plan.worker_name)
    if plan.intent == "pathway_status" and plan.patient_name:
        return read_records(db, user, f"care pathway status for {plan.patient_name}")
    if plan.intent in {"due_followups", "followups_completed", "followups_upcoming"}:
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        query = select(
            FollowupModel.id, FollowupModel.patient_id, PatientModel.name.label("patient"),
            FollowupModel.title, FollowupModel.due_date, FollowupModel.is_completed,
        ).join(PatientModel, PatientModel.id == FollowupModel.patient_id).where(
            patient_scope(user), FollowupModel.is_archived.is_(False),
        )
        if plan.intent == "due_followups":
            query = query.where(FollowupModel.is_completed.is_(False), FollowupModel.due_date <= today)
            label = "due or overdue follow-ups"
        elif plan.intent == "followups_completed":
            query = query.where(FollowupModel.is_completed.is_(True))
            label = "completed follow-ups"
        else:
            query = query.where(FollowupModel.is_completed.is_(False), FollowupModel.due_date > today)
            label = "upcoming follow-ups"
        if plan.patient_name:
            query = query.where(func.lower(PatientModel.name).contains(plan.patient_name.casefold(), autoescape=True))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(FollowupModel.due_date, FollowupModel.id).limit(50))
        return {"answer": f"Found {total} {label}.", "total": total,
                "followups": [dict(row) for row in rows.mappings()], "truncated": total > 50}
    if plan.intent in {"referrals_open", "referrals_attended", "referrals_closed"}:
        query = select(
            PatientReferral.id, PatientReferral.patient_id, PatientModel.name.label("patient"),
            PatientReferral.facility, PatientReferral.referred_on, PatientReferral.status, PatientReferral.outcome,
        ).join(PatientModel, PatientModel.id == PatientReferral.patient_id).where(patient_scope(user))
        statuses = ("referred", "attended") if plan.intent == "referrals_open" else (plan.intent.removeprefix("referrals_"),)
        query = query.where(PatientReferral.status.in_(statuses))
        if plan.patient_name:
            query = query.where(func.lower(PatientModel.name).contains(plan.patient_name.casefold(), autoescape=True))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(PatientReferral.referred_on.desc(), PatientReferral.id.desc()).limit(50))
        return {"answer": f"Found {total} matching referrals.", "total": total,
                "referrals": [dict(row) for row in rows.mappings()], "truncated": total > 50}
    if plan.intent not in {"patients", "patient_count"}:
        return _read_dynamic_records(db, user, plan.intent, plan.patient_name)

    conditions = [patient_scope(user)]
    labels = []
    if plan.patient_name:
        conditions.append(func.lower(PatientModel.name).contains(plan.patient_name.casefold(), autoescape=True))
        labels.append(f"matching {plan.patient_name} patients")
    if plan.village:
        conditions.append(func.lower(PatientModel.village).contains(plan.village.casefold(), autoescape=True))
        labels.append(f"patients in {plan.village}")
    if plan.risk:
        conditions.append(PatientScreening.risk == plan.risk)
        labels.append(f"{plan.risk}-risk patients")
    if plan.anemia_status == "not_assessed":
        conditions.append(PatientModel.anemia_status.is_(None))
        labels.append("patients without an anemia assessment")
    elif plan.anemia_status:
        conditions.append(PatientModel.anemia_status == plan.anemia_status)
        labels.append("patients with " + ("confirmed anemia" if plan.anemia_status == "confirmed" else "a not-anemic assessment"))
    if plan.screening_status == "pending":
        conditions.append(PatientScreening.hb.is_(None))
        labels.append("patients with Hb screening pending")
    elif plan.screening_status == "recorded":
        conditions.append(PatientScreening.hb.is_not(None))
        labels.append("patients with a recorded Hb result")
    query = (
        select(PatientModel.id, PatientModel.name, PatientModel.village, PatientModel.age,
               PatientModel.anemia_status, PatientScreening.risk)
        .outerjoin(PatientScreening, PatientScreening.patient_id == PatientModel.id)
        .where(*conditions)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    if plan.intent == "patient_count":
        label = " and ".join(labels) if labels else "your"
        return {"answer": f"Found {total} {label}.", "count": total}
    rows = db.execute(query.order_by(PatientModel.name, PatientModel.id).limit(50))
    label = " and ".join(labels) if labels else "patients"
    return {"answer": f"Found {total} {label}.", "total": total,
            "patients": [dict(row) for row in rows.mappings()], "truncated": total > 50}


def _read_patient_matches(db: Session, user: UserModel, patient_name: str):
    query = (
        select(PatientModel.id, PatientModel.name, PatientModel.village, PatientModel.age,
               PatientModel.anemia_status, PatientScreening.risk)
        .outerjoin(PatientScreening, PatientScreening.patient_id == PatientModel.id)
        .where(patient_scope(user), func.lower(PatientModel.name).contains(patient_name.casefold(), autoescape=True))
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(PatientModel.name, PatientModel.id).limit(50))
    return {"answer": f"Found {total} matching patient records.", "total": total,
            "patients": [dict(row) for row in rows.mappings()], "truncated": total > 50}


def read_records(
    db: Session, user: UserModel, question: str, worker: str | None = None,
    previous_questions: list[str] | None = None,
):
    pathway_patient = _pathway_patient_search(question)
    if pathway_patient:
        query = (
            select(CarePathwayRun.id, CarePathwayRun.patient_id, PatientModel.name.label("patient"),
                   CarePathwayRun.title, CarePathwayRun.status, CarePathwayRun.updated_at,
                   CarePathwayStep.title.label("step_title"), CarePathwayStep.status.label("step_status"))
            .join(PatientModel, PatientModel.id == CarePathwayRun.patient_id)
            .outerjoin(CarePathwayStep, CarePathwayStep.run_id == CarePathwayRun.id)
            .where(patient_scope(user), func.lower(PatientModel.name).contains(pathway_patient.casefold(), autoescape=True))
            .order_by(CarePathwayRun.updated_at.desc(), CarePathwayRun.id.desc(), CarePathwayStep.position)
        )
        rows = [dict(row) for row in db.execute(query.limit(100)).mappings()]
        if not rows:
            return {"answer": f"No care pathway found for {pathway_patient}.", "total": 0, "pathways": []}
        pathways = {}
        for row in rows:
            item = pathways.setdefault(row["id"], {key: row[key] for key in ("id", "patient_id", "patient", "title", "status", "updated_at")} | {"steps": []})
            if row["step_title"]:
                item["steps"].append({"title": row["step_title"], "status": row["step_status"]})
        return {"answer": f"Found {len(pathways)} care pathway(s) for {rows[0]['patient']}.",
                "total": len(pathways), "pathways": list(pathways.values())}

    patient_name = _patient_name_search(question)
    if patient_name:
        query = (
            select(PatientModel.id, PatientModel.name, PatientModel.village, PatientModel.age,
                   PatientModel.anemia_status, PatientScreening.risk)
            .outerjoin(PatientScreening, PatientScreening.patient_id == PatientModel.id)
            .where(patient_scope(user), func.lower(PatientModel.name).contains(patient_name.casefold(), autoescape=True))
        )
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(PatientModel.name, PatientModel.id).limit(50))
        return {
            "answer": f"Found {total} matching patient records.", "total": total,
            "patients": [dict(row) for row in rows.mappings()], "truncated": total > 50,
        }
    intent = _record_intent(question, is_supervisor(user))
    if intent is None:
        try:
            arguments = call_tool(
                tool=record_query_tool,
                system=(
                    "You plan READ-ONLY queries for SakhiCare, a care coordination app for ASHA workers. "
                    "Available facts: assigned patient demographics, current Hb screening and ASHA-recorded risk, anemia assessment, "
                    "pregnancy dates, planned ANC visits, reported IFA intake, follow-ups, referrals, and Care Pathway status. "
                    "Select exactly one supported query tool. "
                    "When recent conversation questions are provided, use them only to resolve clear references "
                    "such as 'she', 'those patients', or 'that follow-up' in the current question. Answer the current "
                    "question only; do not repeat prior queries or carry forward filters unless the user refers to them. "
                    "If the reference is unclear, return intent=unknown and ask for the patient or topic. "
                    "Never infer a diagnosis, invent records, request SQL, or propose a database change. "
                    "For a write, delete, or update request return intent=unknown; mutations require a separate "
                    "preview and explicit confirmation flow. Use only filters the user clearly asked for. "
                    "A Manager, Executive, or Admin can query only their descendant users; a User can query only their assigned patients."
                ),
                user=(
                    "Recent read-only conversation questions (oldest first):\n"
                    + "\n".join(f"User: {item}" for item in (previous_questions or [])[-3:])
                    + "\nCurrent question (answer this only):\n"
                    + question
                    if previous_questions else question
                ),
            )
            plan = RecordQueryArgs.model_validate(arguments) if arguments else None
        except (HTTPException, ValidationError):
            plan = None
        if plan is None:
            return {"answer": "I can answer questions from the records available to your account, but I couldn't identify which record or care topic you mean. Try naming a patient or asking about Hb results, risk, anemia assessments, referrals, follow-ups, or care pathways. If you meant your previous question, add the patient or topic so I can look it up safely. Record changes need a review and confirmation step.", "total": 0}
        result = _read_planned_records(db, user, plan)
        if result is not None:
            return result
        return {"answer": "I can answer questions from the records available to your account, but I couldn't identify which record or care topic you mean. Try naming a patient or asking about Hb results, risk, anemia assessments, referrals, follow-ups, or care pathways. If you meant your previous question, add the patient or topic so I can look it up safely. Record changes need a review and confirmation step.", "total": 0}
    if intent not in {"patient_count", "patients_by_worker", "worker_patients", "due_followups"}:
        return _read_dynamic_records(db, user, intent)
    question = intent
    scope = patient_scope(user)
    if question == "patient_count" and not is_supervisor(user):
        count = db.scalar(select(func.count()).select_from(PatientModel).where(scope))
        return {"count": count}

    if question in ("patient_count", "patients_by_worker"):
        if not is_supervisor(user):
            raise HTTPException(403, "Supervisor access required")
        rows = db.execute(
            select(UserModel.name.label("worker"), func.count(PatientModel.id).label("count"))
            .outerjoin(PatientModel, PatientModel.asha_user_id == UserModel.id)
            .where(UserModel.id.in_(managed_user_ids(user.id)))
            .group_by(UserModel.id, UserModel.name)
            .order_by(UserModel.name, UserModel.id)
        )
        workers = [dict(row) for row in rows.mappings()]
        result = {"workers": workers}
        if question == "patient_count":
            result["count"] = sum(worker["count"] for worker in workers)
        return result

    if question == "worker_patients":
        if not is_supervisor(user):
            raise HTTPException(403, "Supervisor access required")
        if not worker or not worker.strip():
            raise HTTPException(422, "Enter the ASHA name or username")
        lookup = worker.strip().lower()
        team = select(UserModel).where(UserModel.id.in_(managed_user_ids(user.id)))
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
        .where(scope, FollowupModel.is_archived.is_(False), FollowupModel.is_completed.is_(False), FollowupModel.due_date <= today)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(FollowupModel.due_date, FollowupModel.id).limit(50))
    return {"total": total, "followups": [dict(row) for row in rows.mappings()]}
