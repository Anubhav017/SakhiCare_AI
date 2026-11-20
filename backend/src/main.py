from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from src.User.router import user_router
from src.documents.router import documents_router
from src.followups.router import followups_router
from src.rag.router import ask_router
from src.patients.router import patients_router

from src.tasks.router import task_routers
from src.utils.db import initialize_tables
from src.utils.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        await run_in_threadpool(initialize_tables)
    yield


app = FastAPI(
    title="SakhiCare AI API",
    description="Backend for SakhiCare AI, a screening and follow-up project for ASHA workers.",
    lifespan=lifespan,
)
app.include_router(task_routers)
app.include_router(user_router)
app.include_router(patients_router)
app.include_router(followups_router)
app.include_router(documents_router)
app.include_router(ask_router)


@app.get("/")
def home():
    return {"message": "Hello, World!"}