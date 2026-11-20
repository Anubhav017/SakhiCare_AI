from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class FollowupCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: Annotated[int, Field(gt=0)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    due_date: date


class FollowupUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_completed: bool


class FollowupResponseSchema(FollowupCreateSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_completed: bool
