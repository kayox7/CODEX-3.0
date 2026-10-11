import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON, ForeignKey
from app.database import Base

class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMED_OUT = "TIMED_OUT"

class EscalationLevel(str, enum.Enum):
    APPROVER = "APPROVER"
    RISK_LEAD = "RISK_LEAD"
    EXECUTIVE = "EXECUTIVE"

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    decision_id = Column(String(64), unique=True, index=True, nullable=False)
    agent_id = Column(String(100), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    params = Column(JSON, nullable=False, default=dict)
    data_class = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    records_affected = Column(Integer, nullable=False, default=0)
    reversibility = Column(String(50), nullable=False)
    
    # Risk
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(50), nullable=False)  # LOW, MEDIUM, HIGH, RESTRICTED
    risk_breakdown = Column(JSON, nullable=False, default=dict)
    
    # Evidence pack
    evidence_pack = Column(JSON, nullable=False, default=dict)
    
    # Status & escalation
    status = Column(Enum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING, index=True)
    escalation_level = Column(Enum(EscalationLevel), nullable=False, default=EscalationLevel.APPROVER)
    
    # SLA
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sla_deadline = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    
    # Human resolution
    resolved_by = Column(String(100), nullable=True)  # username of approver
    resolution_reason = Column(String(500), nullable=True)
    
    # Ledger reference
    ledger_hash = Column(String(64), nullable=True)
