from datetime import date as Date, datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PatientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
VillageName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class PatientCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PatientName
    state: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    district: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    block: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    locality_type: Literal["village", "ward"] | None = None
    village: VillageName | None = None
    town: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    ward: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] | None = None
    age: Annotated[int, Field(ge=0, le=130)] | None = None
    consent_obtained: bool
    confirm_possible_duplicate: bool = Field(default=False, exclude=True)

    @model_validator(mode="after")
    def require_consent(self):
        if not self.consent_obtained:
            raise ValueError("Confirm that the patient has given consent before creating this record")
        if self.district and not self.state:
            raise ValueError("Select a state before selecting a district")
        if self.block and not self.district:
            raise ValueError("Select a district before selecting a block")
        if self.locality_type == "village" and not self.village:
            raise ValueError("Select a village")
        if self.locality_type == "ward" and not (self.town and self.ward):
            raise ValueError("Enter the town or city and ward number")
        return self


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


class PatientResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: PatientName
    state: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    district: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    block: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    locality_type: Literal["village", "ward"] | None = None
    village: VillageName | None = None
    town: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    ward: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] | None = None
    age: Annotated[int, Field(ge=0, le=130)] | None = None
    asha_user_id: int
    screening: ScreeningSchema | None = None
    anemia_status: AnemiaStatus | None = None
    consent_obtained: bool | None = None
    consent_recorded_at: datetime | None = None
    consent_recorded_by: int | None = None


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


class PossibleDuplicate(BaseModel):
    id: int
    name: str
    village: str | None
    age: int | None


class PatientAuditEventResponse(BaseModel):
    id: int
    actor_name: str | None
    action: str
    summary: str
    created_at: datetime


class ConsentUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent_obtained: bool


class PregnancyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lmp_date: Date | None = None
    edd_date: Date

    @model_validator(mode="after")
    def validate_recorded_dates(self):
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        if self.lmp_date and self.lmp_date > today:
            raise ValueError("LMP date cannot be in the future")
        if self.lmp_date and self.edd_date <= self.lmp_date:
            raise ValueError("EDD must be after the LMP date")
        return self


class PregnancyStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "closed"]


class PregnancyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    lmp_date: Date | None
    edd_date: Date
    status: Literal["active", "completed", "closed"]
    created_at: datetime


class AntenatalVisitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    due_date: Date
    facility: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None


class AntenatalVisitStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "cancelled"]


class AntenatalVisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pregnancy_id: int
    due_date: Date
    status: Literal["planned", "completed", "cancelled"]
    facility: str | None
    completed_at: datetime | None


class IfaPlanInput(BaseModel):
    """Records an external clinician/facility plan; the app does not prescribe a regimen."""
    model_config = ConfigDict(extra="forbid")
    start_date: Date
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    directions: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]


class IfaPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pregnancy_id: int
    start_date: Date
    source: str
    directions: str
    updated_at: datetime


class IfaIntakeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intake_date: Date
    status: Literal["taken", "missed", "unknown"]

    @model_validator(mode="after")
    def validate_date(self):
        if self.intake_date > datetime.now(timezone(timedelta(hours=5, minutes=30))).date():
            raise ValueError("IFA intake date cannot be in the future")
        return self


class IfaIntakeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pregnancy_id: int
    intake_date: Date
    status: Literal["taken", "missed", "unknown"]
    created_at: datetime


class PregnancyCareResponse(BaseModel):
    pregnancy: PregnancyResponse | None
    visits: list[AntenatalVisitResponse] = Field(default_factory=list)
    ifa_plan: IfaPlanResponse | None = None
    ifa_logs: list[IfaIntakeResponse] = Field(default_factory=list)
