from fastapi import APIRouter, Depends, Header, Query, Request, Response
from typing import Literal

from sqlalchemy.orm import Session

from src.patients.records import read_records
from src.rag.schemas import AskRequest, AskResponse
from src.rag.services import answer, answer_guideline
from src.User.browser_session import get_session, require_session_header
from src.utils.db import get_db
from src.utils.helpers import is_authenticated

ask_router = APIRouter(prefix="/api", tags=["RAG Ask"])


@ask_router.post("/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_sakhicare_session: str | None = Header(None),
):
    response.headers["Cache-Control"] = "no-store"
    if body.source == "guidelines":
        if request.headers.get("Authorization"):
            user = is_authenticated(request, db)
        else:
            require_session_header(x_sakhicare_session)
            user = get_session(request, db)
        return answer_guideline(db, user, body.question, body.language, body.previous_questions)
    user = is_authenticated(request, db)
    return answer(db, user.id, body.question, body.source, body.document_id)

@ask_router.get("/ask/records", tags=["Patient Records"])
def ask_records(
    question: Literal["patient_count", "due_followups", "patients_by_worker", "worker_patients"],
    request: Request,
    response: Response,
    worker: str | None = Query(default=None, min_length=1, max_length=180),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    return read_records(db, get_session(request, db), question, worker)
