import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON
from app.database import Base

class AgentStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"

class DataClass(str, enum.Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class AgentPassport(Base):
    __tablename__ = "agent_passports"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    owner = Column(String(100), nullable=False)  # username of the owner
    purpose = Column(String(500), nullable=False)
    allowed_actions = Column(JSON, nullable=False, default=list)  # list of action strings
    allowed_data_classes = Column(JSON, nullable=False, default=list)  # list of DataClass strings
    max_amount = Column(Float, nullable=False, default=0.0)
    status = Column(Enum(AgentStatus), nullable=False, default=AgentStatus.ACTIVE)
    api_key_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
