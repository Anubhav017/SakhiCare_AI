from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from sqlalchemy.orm import Session

from src.patients.records import read_records
from src.rag.ask_actions import list_pending_actions, resolve_action, stage_action
from src.rag.schemas import AskRecordsRequest, AskRequest, AskResponse
from src.rag.services import answer, answer_guideline
from src.User.browser_session import get_session, require_session_header
from src.utils.db import get_db
from src.utils.helpers import is_authenticated

ask_router = APIRouter(prefix="/api", tags=["RAG Ask"])


class AskChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Annotated[str, Field(min_length=1, max_length=1200)]


class AskChangeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool


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

@ask_router.post("/ask/records", tags=["Patient Records"])
def ask_records(
    body: AskRecordsRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    return read_records(db, get_session(request, db), body.question, body.worker)


@ask_router.get("/ask/records/actions/pending")
def pending_ask_actions(request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return list_pending_actions(db, get_session(request, db))


@ask_router.post("/ask/records/actions", dependencies=[Depends(require_session_header)])
def propose_ask_action(
    body: AskChangeRequest, request: Request, response: Response,
    db: Session = Depends(get_db),
):
    user = get_session(request, db)
    graph = getattr(request.app.state, "ask_action_graph", None)
    if graph is None:
        raise HTTPException(503, "Ask change approvals are not available. Restart the API and try again.")
    response.headers["Cache-Control"] = "private, no-store"
    return stage_action(db, user, body.question, graph)


@ask_router.post("/ask/records/actions/{draft_id}/decision", dependencies=[Depends(require_session_header)])
def decide_ask_action(
    draft_id: str, body: AskChangeDecision, request: Request, response: Response,
    db: Session = Depends(get_db),
):
    user = get_session(request, db)
    graph = getattr(request.app.state, "ask_action_graph", None)
    if graph is None:
        raise HTTPException(503, "Ask change approvals are not available. Restart the API and try again.")
    response.headers["Cache-Control"] = "private, no-store"
    return resolve_action(db, user, draft_id, body.approved, graph)
