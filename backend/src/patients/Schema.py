from datetime import date as Date, datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PatientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
VillageName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class PatientCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PatientName
    village: VillageName | None = None
    age: Annotated[int, Field(ge=0, le=130)] | None = None


class ScreeningMeasurement(BaseModel):
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


class ScreeningSchema(ScreeningMeasurement):
    risk: Literal["low", "moderate", "high"] | None = None


AnemiaStatus = Literal["confirmed", "not_anemic"]


class PatientResponseSchema(PatientCreateSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asha_user_id: int
    screening: ScreeningSchema | None = None
    anemia_status: AnemiaStatus | None = None


class HbReadingSchema(ScreeningMeasurement):
    id: int
    hb: Annotated[float, Field(gt=0, allow_inf_nan=False)]


class AnemiaAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: AnemiaStatus | None


class ReferralCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facility: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    referred_on: Date

    @model_validator(mode="after")
    def validate_date(self):
        if self.referred_on > datetime.now(timezone(timedelta(hours=5, minutes=30))).date():
            raise ValueError("Referral date cannot be in the future")
        return self


class ReferralUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["referred", "attended", "closed"]
    outcome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = None

    @model_validator(mode="after")
    def validate_outcome(self):
        if (self.status == "closed") != (self.outcome is not None):
            raise ValueError("Enter an outcome when closing a referral")
        return self


class ReferralResponse(ReferralCreate, ReferralUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: int
