from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from starlette.concurrency import run_in_threadpool

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.User.router import user_router
from src.documents.router import documents_router
from src.followups.router import followups_router
from src.rag.router import ask_router
from src.patients.router import patients_router
from src.pathways.models import CarePathwayRun, CarePathwayStep  # noqa: F401
from src.rag.action_models import AskActionDraft  # noqa: F401
from src.pathways.router import pathways_router

from src.utils.db import get_db, initialize_tables
from src.utils.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        await run_in_threadpool(initialize_tables)
    from src.rag.ask_actions import open_action_graph

    with open_action_graph() as graph:
        app.state.ask_action_graph = graph
        yield


app = FastAPI(
    title="SakhiCare AI API",
    description="Backend for SakhiCare AI, a screening and follow-up project for ASHA workers.",
    lifespan=lifespan,
)
app.include_router(user_router)
app.include_router(patients_router)
app.include_router(followups_router)
app.include_router(pathways_router)
app.include_router(documents_router)
app.include_router(ask_router)


@app.get("/healthz", include_in_schema=False)
def healthz(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
