from typing import Literal

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


class BrowserLoginSchema(UserLoginSchema):
    remember: bool = False


class BrowserAccountSchema(UserResponseSchema):
    role: Literal["asha", "super_admin"]


class ManagedAshaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str
