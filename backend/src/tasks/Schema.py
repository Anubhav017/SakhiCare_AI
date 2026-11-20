from pydantic import BaseModel

class TaskSchema(BaseModel):
    title: str
    description: str
    is_completed: bool

    
class TaskResponseSchema(TaskSchema):
    id: int
    title: str
    description: str
    is_completed: bool
    user_id: int