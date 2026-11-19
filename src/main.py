from fastapi import FastAPI
from src.utils.db import Base, engine
from src.tasks.router import task_routers

from src.User.router import user_router

Base.metadata.create_all(bind=engine)


app = FastAPI(title="Task Management Application", description="A simple task management application")
app.include_router(task_routers)
app.include_router(user_router)


@app.get("/")
def home():
    return {"message": "Hello, World!"}