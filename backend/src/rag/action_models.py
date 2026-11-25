from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, JSON, String, func

from src.utils.db import Base


class AskActionDraft(Base):
    """An ASHA-reviewed, short-lived proposal to change a care record."""

    __tablename__ = "ask_action_drafts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'applied', 'cancelled', 'expired', 'failed')",
            name="ck_ask_action_draft_status",
        ),
    )

    id = Column(String(36), primary_key=True)
    actor_user_id = Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(40), nullable=False)
    payload = Column(JSON, nullable=False)
    preview = Column(JSON, nullable=False)
    status = Column(String(12), nullable=False, server_default="pending", index=True)
    result = Column(JSON)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True))
