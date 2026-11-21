from sqlalchemy import CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from src.User.models import UserModel
from src.utils.db import Base


class PatientModel(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    village = Column(String(100))
    age = Column(Integer)
    asha_user_id = Column(Integer, ForeignKey(UserModel.id), nullable=False, index=True)

    registered_at = Column(DateTime(timezone=True), server_default=func.now())
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
