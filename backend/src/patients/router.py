from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from src.User.browser_session import get_session, require_session_header
from src.patients import controller
from src.patients.Schema import HbReadingSchema, PatientCreateSchema, PatientResponseSchema, ScreeningSchema
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
    if asha.role != "asha":
        raise HTTPException(403, "Only ASHA workers can register patients")
    return controller.create_patient(db, asha.id, body)


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
    if user.role != "asha":
        raise HTTPException(403, "Only ASHA workers can record Hb")
    return controller.save_screening(db, user, patient_id, body)


@patients_router.get("/{patient_id}/screening/history", response_model=list[HbReadingSchema])
def screening_history(patient_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    user = get_session(request, db)
    response.headers["Cache-Control"] = "private, no-store"
    return controller.list_hb_readings(db, user, patient_id)
