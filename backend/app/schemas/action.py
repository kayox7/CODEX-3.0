from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class ActionRequest(BaseModel):
    agent_id: str
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    amount: float = 0.0
    records_affected: int = 0
    data_class: str = "public"
    reversibility: str = "partially"  # reversible | partially | irreversible

class ActionDecisionResponse(BaseModel):
    decision: str  # ALLOW | PENDING_APPROVAL | BLOCKED | HUMAN_ONLY
    decision_id: str
    risk_score: float
    risk_level: str
    explanation: str
    risk_breakdown: Optional[Dict[str, Any]] = None
    evidence_pack: Optional[Dict[str, Any]] = None
    ledger_hash: Optional[str] = None

class ActionExecutionReport(BaseModel):
    agent_id: str
    decision_id: str
    action: str
    status: str  # SUCCESS | FAILED
    result_summary: Optional[str] = None
