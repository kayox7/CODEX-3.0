from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ApproveRequest(BaseModel):
    reason: Optional[str] = "Approved by human reviewer"

class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Rejection reason is mandatory")

class ApprovalResponse(BaseModel):
    id: int
    decision_id: str
    agent_id: str
    action: str
    params: Dict[str, Any]
    data_class: str
    amount: float
    records_affected: int
    reversibility: str
    risk_score: float
    risk_level: str
    risk_breakdown: Dict[str, Any]
    evidence_pack: Dict[str, Any]
    status: str  # PENDING | APPROVED | REJECTED | TIMED_OUT
    escalation_level: str  # APPROVER | RISK_LEAD | EXECUTIVE
    created_at: str
    sla_deadline: str
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_reason: Optional[str] = None
    ledger_hash: Optional[str] = None

class EscalationCheckResponse(BaseModel):
    checked_at: str
    escalated_count: int
    timed_out_count: int
    escalated: List[Dict[str, Any]]
    timed_out: List[Dict[str, Any]]
