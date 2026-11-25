from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from src.User.browser_session import get_session, require_session_header
from src.pathways import service
from src.pathways.schemas import CarePathwayResponse, CarePathwayStepUpdate
from src.utils.db import get_db

pathways_router = APIRouter(prefix="/pathways", tags=["Care Pathways"])


@pathways_router.get("", response_model=list[CarePathwayResponse])
def read_pathways(request: Request, response: Response, patient_id: int | None = None,
                  db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return service.list_pathways(db, get_session(request, db), patient_id)


@pathways_router.patch("/{run_id}/steps/{step_id}", response_model=CarePathwayResponse,
                       dependencies=[Depends(require_session_header)])
def change_step(run_id: int, step_id: int, body: CarePathwayStepUpdate,
                request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    user = get_session(request, db)
    if user.role != "asha":
        raise HTTPException(403, "Only ASHA workers can update pathway steps")
    return service.update_step(db, user, run_id, step_id, body.completed)
