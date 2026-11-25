from sqlalchemy import Boolean, Column, Date, ForeignKey, Index, Integer, String, false

from src.patients.models import PatientModel
from src.utils.db import Base


class FollowupModel(Base):
    __tablename__ = "patient_followups"
    __table_args__ = (Index("ix_patient_followups_patient_due", "patient_id", "due_date"),)

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey(PatientModel.id, ondelete="CASCADE"), nullable=False)
    title = Column(String(160), nullable=False)
    due_date = Column(Date, nullable=False)
    is_completed = Column(Boolean, nullable=False, server_default=false())
    is_archived = Column(Boolean, nullable=False, server_default=false())
