from sqlalchemy import CheckConstraint, Column, Date, Float, ForeignKey, Integer, String, UniqueConstraint
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

    screening = relationship("PatientScreening", uselist=False, lazy="selectin")


class PatientScreening(Base):
    __tablename__ = "patient_screenings"

    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, nullable=False)
    hb = Column(Float)
    method = Column(String(100), nullable=False)
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
