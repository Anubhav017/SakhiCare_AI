from fastapi import APIRouter, Depends, status
from src.tasks import controller
from src.User.models import UserModel
from src.utils.helpers import is_authenticated
from src.tasks.Schema import TaskSchema, TaskResponseSchema
from src.utils.db import get_db
from sqlalchemy.orm import Session

task_routers = APIRouter(prefix = "/task")

@task_routers.post("/create", response_model=TaskResponseSchema, status_code=status.HTTP_201_CREATED)
def Create_task(body: TaskSchema, db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    return controller.Create_task(body, db, user)

@task_routers.get("/all_tasks", response_model=list[TaskResponseSchema], status_code=status.HTTP_200_OK)
def get_all_task(db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    return controller.get_all_task(db, user)


@task_routers.get("/task_id/{task_id}", response_model=TaskResponseSchema, status_code=status.HTTP_200_OK)
def get_task_by_id(task_id: int, db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    return controller.get_task_by_id(task_id, db, user)

@task_routers.put("/task_id/{task_id}", response_model=TaskResponseSchema, status_code=status.HTTP_201_CREATED)
def update_task(task_id: int, body: TaskSchema, db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    return controller.update_task(task_id, body, user, db)  

@task_routers.delete("/task_id/{task_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    return controller.delete_task(task_id, db, user)