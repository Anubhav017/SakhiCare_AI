from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from src.followups import controller
from src.followups.Schema import FollowupCreateSchema, FollowupResponseSchema, FollowupUpdateSchema
from src.User.browser_session import get_session, require_session_header
from src.utils.db import get_db

followups_router = APIRouter(prefix="/followups", tags=["Follow-ups"])


def _require_asha(request: Request, db: Session):
    user = get_session(request, db)
    if user.role != "user":
        raise HTTPException(403, "Only ASHA workers can change follow-ups")
    return user


@followups_router.get("", response_model=list[FollowupResponseSchema])
def list_followups(request: Request, response: Response, db: Session = Depends(get_db)):
    user = get_session(request, db)
    response.headers["Cache-Control"] = "no-store"
    return controller.list_followups(db, user)


@followups_router.post(
    "", status_code=201, response_model=FollowupResponseSchema,
    dependencies=[Depends(require_session_header)],
)
def create_followup(body: FollowupCreateSchema, request: Request, response: Response, db: Session = Depends(get_db)):
    user = _require_asha(request, db)
    response.headers["Cache-Control"] = "no-store"
    return controller.create_followup(db, user, body)


@followups_router.patch(
    "/{followup_id}", response_model=FollowupResponseSchema,
    dependencies=[Depends(require_session_header)],
)
def update_followup(
    followup_id: int, body: FollowupUpdateSchema, request: Request, response: Response,
    db: Session = Depends(get_db),
):
    user = _require_asha(request, db)
    response.headers["Cache-Control"] = "no-store"
    return controller.update_followup(db, user, followup_id, body.is_completed)
