from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from src.utils.db import Base


class CarePathwayRun(Base):
    __tablename__ = "care_pathway_runs"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'paused', 'cancelled')", name="ck_care_pathway_run_status"),
        UniqueConstraint("source_key", name="uq_care_pathway_source_key"),
    )

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    pathway_key = Column(String(40), nullable=False)
    title = Column(String(140), nullable=False)
    source_key = Column(String(180), nullable=False)
    status = Column(String(12), nullable=False, server_default="active", index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    steps = relationship("CarePathwayStep", back_populates="run", cascade="all, delete-orphan", order_by="CarePathwayStep.position")


class CarePathwayStep(Base):
    __tablename__ = "care_pathway_steps"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'completed', 'skipped')", name="ck_care_pathway_step_status"),
        UniqueConstraint("run_id", "position", name="uq_care_pathway_step_position"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("care_pathway_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    title = Column(String(180), nullable=False)
    status = Column(String(12), nullable=False, server_default="pending")
    due_date = Column(Date)
    completed_at = Column(DateTime(timezone=True))
    completed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    run = relationship("CarePathwayRun", back_populates="steps")
