import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum
from app.database import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    APPROVER = "approver"
    RISK_LEAD = "risk_lead"
    EXECUTIVE = "executive"
    AUDITOR = "auditor"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.AUDITOR)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
