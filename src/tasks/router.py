from fastapi import APIRouter, Depends
from src.tasks import controller
from src.tasks.Schema import TaskSchema
from src.utils.db import get_db
from sqlalchemy.orm import Session

task_routers = APIRouter(prefix = "/task")

@task_routers.post("/create")
def Create_task(body:TaskSchema, db: Session = Depends(get_db)):
    return controller.Create_task(body, db)

@task_routers.get("/all_tasks")
def get_task(db: Session = Depends(get_db)):
    return controller.get_task(db)
