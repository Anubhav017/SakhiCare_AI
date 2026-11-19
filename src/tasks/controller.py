
from fastapi import HTTPException
from requests import session
from src.utils.helpers import is_authenticated
from src.tasks.Schema import TaskSchema

from sqlalchemy.orm import Session
from src.tasks.models import TaskModel

from src.User.models import UserModel

def Create_task(body: TaskSchema, db: Session, user: UserModel):
    data  = body.model_dump()
    task = TaskModel(title=data['title'],
                    description=data['description'], is_completed=data['is_completed'], user_id=user.id)

    db.add(task)
    db.commit()
    db.refresh(task)

    return task

def get_all_task(db: Session, user: UserModel):
    task = db.query(TaskModel).filter(TaskModel.user_id == user.id).all()
    return task

def get_task_by_id(task_id: int, db: Session):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

def update_task(task_id: int, body: TaskSchema, user: UserModel, db: Session):
    task = db.query(TaskModel).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.user_id != user.id:
        raise HTTPException(status_code=403, detail="You are not the owner of this task")

    data = body.model_dump()
    for key, value in data.items():
        setattr(task, key, value)

    db.add(task)
    db.commit()
    db.refresh(task)

    return task

def delete_task(task_id: int, db: Session, user: UserModel):
    task = db.query(TaskModel).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.user_id != user.id:
        raise HTTPException(status_code=403, detail="You are not the owner of this task")

    db.delete(task)
    db.commit()

    return None
