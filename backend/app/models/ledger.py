import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.database import Base

class LedgerEventType(str, enum.Enum):
    GENESIS = "GENESIS"
    AGENT_REGISTERED = "AGENT_REGISTERED"
    AGENT_UPDATED = "AGENT_UPDATED"
    AGENT_PAUSED = "AGENT_PAUSED"
    AGENT_RESUMED = "AGENT_RESUMED"
    KILL_SWITCH_TRIGGERED = "KILL_SWITCH_TRIGGERED"
    ACTION_EVALUATED = "ACTION_EVALUATED"
    ACTION_ALLOWED = "ACTION_ALLOWED"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_ESCALATED = "APPROVAL_ESCALATED"
    APPROVAL_TIMEOUT = "APPROVAL_TIMEOUT"
    ACTION_APPROVED = "ACTION_APPROVED"
    ACTION_REJECTED = "ACTION_REJECTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    SYSTEM_ALERT = "SYSTEM_ALERT"

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    actor = Column(String(100), nullable=False, index=True)  # agent_id, username, or "system"
    payload = Column(JSON, nullable=False)
    prev_hash = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False, unique=True, index=True)
