from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from src.User.browser_session import get_session, require_session_header
from src.User.models import UserModel
from src.User.roles import is_supervisor
from src.patients import controller
from src.patients.Schema import (AntenatalVisitCreate, AntenatalVisitResponse, AntenatalVisitStatusUpdate,
                                 AnemiaAssessment, ConsentUpdateSchema, IfaIntakeInput, IfaIntakeResponse,
                                 IfaPlanInput, IfaPlanResponse, PatientAuditEventResponse, PregnancyCareResponse,
                                 PregnancyCreate, PregnancyResponse, PregnancyStatusUpdate, ReferralCreate,
                                 ReferralResponse, ReferralUpdate, HbReadingSchema, PatientCreateSchema,
                                 PatientResponseSchema, ScreeningSchema)
from src.utils.db import get_db

patients_router = APIRouter(prefix="/patients", tags=["Patients"])


@patients_router.get("", response_model=list[PatientResponseSchema])
def list_patients(request: Request, response: Response, db: Session = Depends(get_db)):
    asha = get_session(request, db)
    response.headers["Cache-Control"] = "no-store"
    return controller.list_patients(db, asha)


@patients_router.post(
    "", response_model=PatientResponseSchema, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_session_header)],
)
def create_patient(
    body: PatientCreateSchema, request: Request, response: Response, db: Session = Depends(get_db)
):
    asha = get_session(request, db)
    response.headers["Cache-Control"] = "no-store"
    if asha.role != "user":
        raise HTTPException(403, "Only ASHA workers can register patients")
    return controller.create_patient(db, asha, body)


@patients_router.get("/dashboard-summary")
def read_dashboard_summary(request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.dashboard_summary(db, get_session(request, db))


@patients_router.get("/team-report")
def read_team_report(
    request: Request, response: Response, db: Session = Depends(get_db),
    start: date | None = None, end: date | None = None,
    worker_id: int | None = None, village: str | None = None,
):
    user = get_session(request, db)
    if not is_supervisor(user):
        raise HTTPException(403, "Supervisor access required for team reports")
    if start is not None and end is not None and start > end:
        raise HTTPException(422, "Start date must be on or before end date")
    response.headers["Cache-Control"] = "private, no-store"
    return controller.team_report(db, user, start, end, worker_id, village)


@patients_router.get("/{patient_id}/activity", response_model=list[PatientAuditEventResponse])
def read_patient_activity(patient_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    user = get_session(request, db)
    response.headers["Cache-Control"] = "private, no-store"
    return controller.list_patient_activity(db, user, patient_id)


@patients_router.get("/{patient_id}", response_model=PatientResponseSchema)
def read_patient(patient_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    user = get_session(request, db)
    response.headers["Cache-Control"] = "no-store"
    return controller.get_patient(db, user, patient_id)


@patients_router.put(
    "/{patient_id}/screening", response_model=ScreeningSchema,
    dependencies=[Depends(require_session_header)],
)
def save_screening(
    patient_id: int, body: ScreeningSchema, request: Request, response: Response,
    db: Session = Depends(get_db),
):
    user = get_session(request, db)
    response.headers["Cache-Control"] = "private, no-store"
    if user.role != "user":
        raise HTTPException(403, "Only ASHA workers can record Hb")
    return controller.save_screening(db, user, patient_id, body)


@patients_router.get("/{patient_id}/screening/history", response_model=list[HbReadingSchema])
def screening_history(patient_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    user = get_session(request, db)
    response.headers["Cache-Control"] = "private, no-store"
    return controller.list_hb_readings(db, user, patient_id)


MAX_REPORT_BYTES = 10 * 1024 * 1024


@patients_router.post(
    "/{patient_id}/reports", status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_session_header)],
)
def upload_patient_report(
    patient_id: int, request: Request, response: Response,
    file: UploadFile = File(...), db: Session = Depends(get_db),
):
    user = get_session(request, db)
    if user.role != "user":
        raise HTTPException(403, "Only ASHA workers can upload patient reports")
    patient = controller.get_patient(db, user, patient_id)
    filename = (file.filename or "").replace(chr(92), "/").rsplit("/", 1)[-1]
    if not filename.lower().endswith(".pdf") or len(filename) > 255 or not filename.isprintable():
        raise HTTPException(400, "Choose a PDF with a valid filename")
    pdf = file.file.read(MAX_REPORT_BYTES + 1)
    if len(pdf) > MAX_REPORT_BYTES:
        raise HTTPException(413, "PDFs must be 10 MB or smaller")
    if not pdf.startswith(b"%PDF-"):
        raise HTTPException(400, "Choose a valid PDF file")
    response.headers["Cache-Control"] = "private, no-store"
    return {"id": controller.save_patient_report(db, user, patient, filename, pdf)}


def require_asha_session(request: Request, db: Session) -> UserModel:
    user = get_session(request, db)
    if user.role != "user":
        raise HTTPException(403, "Only ASHA workers can update patient assessments and referrals")
    return user


@patients_router.get("/{patient_id}/pregnancy", response_model=PregnancyCareResponse)
def read_pregnancy_care(patient_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.pregnancy_care(db, get_session(request, db), patient_id)


@patients_router.post("/{patient_id}/pregnancy", response_model=PregnancyResponse, status_code=201,
                      dependencies=[Depends(require_session_header)])
def add_pregnancy(patient_id: int, body: PregnancyCreate, request: Request,
                  response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.create_pregnancy(db, require_asha_session(request, db), patient_id, body)


@patients_router.patch("/{patient_id}/pregnancy/{pregnancy_id}", response_model=PregnancyResponse,
                       dependencies=[Depends(require_session_header)])
def change_pregnancy_status(patient_id: int, pregnancy_id: int, body: PregnancyStatusUpdate, request: Request,
                            response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.update_pregnancy_status(db, require_asha_session(request, db), patient_id, pregnancy_id, body)


@patients_router.post("/{patient_id}/pregnancy/{pregnancy_id}/anc-visits", response_model=AntenatalVisitResponse,
                      status_code=201, dependencies=[Depends(require_session_header)])
def add_anc_visit(patient_id: int, pregnancy_id: int, body: AntenatalVisitCreate, request: Request,
                  response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.schedule_anc_visit(db, require_asha_session(request, db), patient_id, pregnancy_id, body)


@patients_router.patch("/{patient_id}/pregnancy/{pregnancy_id}/anc-visits/{visit_id}", response_model=AntenatalVisitResponse,
                       dependencies=[Depends(require_session_header)])
def change_anc_visit(patient_id: int, pregnancy_id: int, visit_id: int, body: AntenatalVisitStatusUpdate,
                     request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.update_anc_visit(db, require_asha_session(request, db), patient_id, pregnancy_id, visit_id, body.status)


@patients_router.put("/{patient_id}/pregnancy/{pregnancy_id}/ifa-plan", response_model=IfaPlanResponse,
                     dependencies=[Depends(require_session_header)])
def save_ifa_plan(patient_id: int, pregnancy_id: int, body: IfaPlanInput, request: Request,
                  response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.save_ifa_plan(db, require_asha_session(request, db), patient_id, pregnancy_id, body)


@patients_router.put("/{patient_id}/pregnancy/{pregnancy_id}/ifa-intake", response_model=IfaIntakeResponse,
                     dependencies=[Depends(require_session_header)])
def save_ifa_intake(patient_id: int, pregnancy_id: int, body: IfaIntakeInput, request: Request,
                    response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.record_ifa_intake(db, require_asha_session(request, db), patient_id, pregnancy_id, body)


@patients_router.put("/{patient_id}/anemia-assessment", response_model=PatientResponseSchema,
                     dependencies=[Depends(require_session_header)])
def update_anemia_assessment(patient_id: int, body: AnemiaAssessment, request: Request,
                             response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.record_anemia_assessment(db, require_asha_session(request, db), patient_id, body)


@patients_router.put("/{patient_id}/consent", response_model=PatientResponseSchema,
                     dependencies=[Depends(require_session_header)])
def update_patient_consent(patient_id: int, body: ConsentUpdateSchema, request: Request,
                           response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.record_consent(db, require_asha_session(request, db), patient_id, body.consent_obtained)


@patients_router.get("/{patient_id}/referrals", response_model=list[ReferralResponse])
def read_referrals(patient_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.list_referrals(db, get_session(request, db), patient_id)


@patients_router.post("/{patient_id}/referrals", response_model=ReferralResponse, status_code=201,
                      dependencies=[Depends(require_session_header)])
def add_referral(patient_id: int, body: ReferralCreate, request: Request,
                 response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.create_referral(db, require_asha_session(request, db), patient_id, body)


@patients_router.put("/{patient_id}/referrals/{referral_id}", response_model=ReferralResponse,
                     dependencies=[Depends(require_session_header)])
def change_referral(patient_id: int, referral_id: int, body: ReferralUpdate, request: Request,
                    response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return controller.update_referral(db, require_asha_session(request, db), patient_id, referral_id, body)
