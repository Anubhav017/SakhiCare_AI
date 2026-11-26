from typing import Literal

from pydantic import ConfigDict, BaseModel, Field

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
    role: Literal["user", "manager", "executive", "admin", "super_admin"] | None = None


class BrowserAccountSchema(UserResponseSchema):
    role: Literal["user", "manager", "executive", "admin", "super_admin"]


class ManagedAshaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str


class ManagedMemberSchema(BaseModel):
    id: int
    name: str
    username: str
    email: str
    role: Literal["user", "manager", "executive", "admin"]
    reports_to_id: int | None


class MemberAccessUpdateSchema(BaseModel):
    role: Literal["user", "manager", "executive"]
    reports_to_id: int


class AdminOnboardingSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class OnboardedAdminSchema(UserResponseSchema):
    role: Literal["admin"]
