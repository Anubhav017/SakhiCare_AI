from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CarePathwayStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    title: str
    status: Literal["pending", "completed", "skipped"]
    due_date: date | None
    completed_at: datetime | None


class CarePathwayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    pathway_key: str
    title: str
    status: Literal["active", "completed", "paused", "cancelled"]
    created_at: datetime
    updated_at: datetime
    steps: list[CarePathwayStepResponse]


class CarePathwayStepUpdate(BaseModel):
    completed: bool
