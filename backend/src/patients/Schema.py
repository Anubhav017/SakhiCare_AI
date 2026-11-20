from datetime import date as Date, datetime, timedelta, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PatientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
VillageName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class PatientCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PatientName
    village: VillageName | None = None
    age: Annotated[int, Field(ge=0, le=130)] | None = None


class ScreeningSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    date: Date
    hb: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    method: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""

    @model_validator(mode="after")
    def validate_measurement(self):
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        if self.date > today:
            raise ValueError("Screening date cannot be in the future")
        if (self.hb is None) == bool(self.method):
            raise ValueError("Enter a measurement method only when Hb is measured")
        return self


class PatientResponseSchema(PatientCreateSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asha_user_id: int
    screening: ScreeningSchema | None = None


class HbReadingSchema(ScreeningSchema):
    id: int
    hb: Annotated[float, Field(gt=0, allow_inf_nan=False)]
