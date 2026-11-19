from pydantic import BaseModel

class RequestSchema(BaseModel):
    name: str
    email: str

