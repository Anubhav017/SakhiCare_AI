
from requests import session
from src.tasks.Schema import TaskSchema
from sqlalchemy.orm import Session
from src.tasks.models import TaskModel

def Create_task(body: TaskSchema, db: Session):
    data  = body.model_dump()
    task = TaskModel(title=data['title'],
                    description=data['description'], is_completed=data['is_completed'])

    db.add(task)
    db.commit()
    db.refresh(task)

    return {"status": "Task Created Successfully", "task": task}

def get_task(db: Session):
    task = db.query(TaskModel).all()
    return {"status": "Task Fetched Successfully", "task": task}
