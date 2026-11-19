from pydantic import ConfigDict, BaseModel

class UserSchema(BaseModel):
    name: str
    username: str
    password: str
    email: str

class UserResponseSchema(BaseModel):
    name: str
    username: str
    email: str
    id: int

class UserLoginSchema(BaseModel):
    username: str
    password: str

class UserLoginResponseSchema(BaseModel):
    token: str
    