from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String
from src.utils.db import Base

class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('asha', 'super_admin')", name="ck_users_role"),
    )
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    username = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    role = Column(String(20), nullable=False, server_default="asha")
    admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
