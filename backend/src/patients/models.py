from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, UniqueConstraint, func, text
from sqlalchemy.orm import relationship

from src.User.models import UserModel
from src.utils.db import Base


class PatientModel(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    state = Column(String(100))
    district = Column(String(120))
    block = Column(String(120))
    locality_type = Column(String(10))
    village = Column(String(100))
    town = Column(String(120))
    ward = Column(String(30))
    age = Column(Integer)
    asha_user_id = Column(Integer, ForeignKey(UserModel.id), nullable=False, index=True)

    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    consent_obtained = Column(Boolean)
    consent_recorded_at = Column(DateTime(timezone=True))
    consent_recorded_by = Column(Integer, ForeignKey(UserModel.id, ondelete="SET NULL"))
    anemia_status = Column(String(12), CheckConstraint("anemia_status IN ('confirmed', 'not_anemic')", name="ck_patient_anemia_status"))

    screening = relationship("PatientScreening", uselist=False, lazy="selectin")


class PatientScreening(Base):
    __tablename__ = "patient_screenings"

    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, nullable=False)
    hb = Column(Float)
    method = Column(String(100), nullable=False)
    risk = Column(String(8), CheckConstraint("risk IN ('low', 'moderate', 'high')", name="ck_screening_risk"))
    __table_args__ = (
        CheckConstraint(
            "(hb IS NULL AND method = '') OR (hb IS NOT NULL AND hb > 0 AND hb < 'Infinity'::float8 AND length(trim(method)) > 0)",
            name="ck_patient_screening_measurement",
        ),
    )


class PregnancyEpisode(Base):
    """A pregnancy recorded for a patient; dates are entered from care records."""
    __tablename__ = "patient_pregnancies"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    lmp_date = Column(Date)
    edd_date = Column(Date, nullable=False)
    status = Column(String(12), nullable=False, server_default="active", index=True)
    recorded_by_user_id = Column(Integer, ForeignKey(UserModel.id, ondelete="SET NULL"), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'closed')", name="ck_patient_pregnancy_status"),
        Index("uq_patient_pregnancy_active", "patient_id", unique=True, postgresql_where=text("status = 'active'")),
    )


class AntenatalVisit(Base):
    __tablename__ = "patient_anc_visits"

    id = Column(Integer, primary_key=True)
    pregnancy_id = Column(Integer, ForeignKey("patient_pregnancies.id", ondelete="CASCADE"), nullable=False, index=True)
    due_date = Column(Date, nullable=False)
    followup_id = Column(Integer, ForeignKey("patient_followups.id", ondelete="SET NULL"), unique=True)
    status = Column(String(12), nullable=False, server_default="planned", index=True)
    facility = Column(String(120))
    recorded_by_user_id = Column(Integer, ForeignKey(UserModel.id, ondelete="SET NULL"), index=True)
    completed_at = Column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'completed', 'cancelled')", name="ck_patient_anc_visit_status"),
    )


class IfaPlan(Base):
    """ASHA-recorded IFA instructions copied from an authorized care plan."""
    __tablename__ = "patient_ifa_plans"

    id = Column(Integer, primary_key=True)
    pregnancy_id = Column(Integer, ForeignKey("patient_pregnancies.id", ondelete="CASCADE"), nullable=False, unique=True)
    start_date = Column(Date, nullable=False)
    source = Column(String(120), nullable=False)
    directions = Column(String(240), nullable=False)
    recorded_by_user_id = Column(Integer, ForeignKey(UserModel.id, ondelete="SET NULL"), index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class IfaIntakeLog(Base):
    __tablename__ = "patient_ifa_intake_logs"

    id = Column(Integer, primary_key=True)
    pregnancy_id = Column(Integer, ForeignKey("patient_pregnancies.id", ondelete="CASCADE"), nullable=False, index=True)
    intake_date = Column(Date, nullable=False)
    status = Column(String(10), nullable=False)
    recorded_by_user_id = Column(Integer, ForeignKey(UserModel.id, ondelete="SET NULL"), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        CheckConstraint("status IN ('taken', 'missed', 'unknown')", name="ck_patient_ifa_intake_status"),
        UniqueConstraint("pregnancy_id", "intake_date", name="uq_patient_ifa_intake_day"),
    )


class HbReading(Base):
    __tablename__ = "patient_hb_readings"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    hb = Column(Float, nullable=False)
    method = Column(String(100), nullable=False)
    __table_args__ = (
        UniqueConstraint("patient_id", "date", "hb", "method", name="uq_patient_hb_reading"),
    )


class PatientReport(Base):
    __tablename__ = "patient_reports"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    pdf = Column(LargeBinary, nullable=False)


class PatientReferral(Base):
    __tablename__ = "patient_referrals"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    facility = Column(String(120), nullable=False)
    referred_on = Column(Date, nullable=False)
    status = Column(String(12), nullable=False)
    outcome = Column(String(500))
    __table_args__ = (
        CheckConstraint(
            "(status IN ('referred', 'attended') AND outcome IS NULL) OR "
            "(status = 'closed' AND outcome IS NOT NULL AND length(trim(outcome)) > 0)",
            name="ck_patient_referral_outcome",
        ),
    )


class PatientAuditEvent(Base):
    __tablename__ = "patient_audit_events"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey(UserModel.id, ondelete="SET NULL"), index=True)
    action = Column(String(80), nullable=False)
    summary = Column(String(240), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
