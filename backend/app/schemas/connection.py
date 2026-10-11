"""Pydantic schemas for Connected AI Agents feature."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ConnectionCreateRequest(BaseModel):
    name: str
    provider: str  # anthropic | google_gemini | openai | deepseek | custom_openai | mock
    api_key: str
    model: str  # free text, e.g. "gpt-4o", "claude-3-5-sonnet", etc.
    base_url: Optional[str] = None
    system_prompt: Optional[str] = None
    allowed_actions: List[str] = Field(default_factory=lambda: ["issue_refund", "update_record"])
    allowed_data_classes: List[str] = Field(default_factory=lambda: ["public", "internal"])
    max_amount: float = 5000.0

class ConnectionUpdateRequest(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    system_prompt: Optional[str] = None
    allowed_actions: Optional[List[str]] = None
    allowed_data_classes: Optional[List[str]] = None
    max_amount: Optional[float] = None

class ConnectionRotateKeyRequest(BaseModel):
    api_key: str

class ConnectionRunRequest(BaseModel):
    task: str

class ConnectionResponse(BaseModel):
    id: int
    name: str
    provider: str
    base_url: str
    model: str
    key_last4: str
    agent_id: str
    system_prompt: Optional[str] = None
    allowed_actions: List[str]
    allowed_data_classes: List[str]
    max_amount: float
    status: str
    created_by: str
    created_at: str
    last_used_at: Optional[str] = None
    last_test_status: Optional[str] = None
    request_count: int = 0
    blocked_count: int = 0

class ConnectionTestResponse(BaseModel):
    status: str  # valid | invalid_key | rate_limited | unreachable | error
    message: str

class ToolDecisionDetail(BaseModel):
    tool: str
    arguments_summary: Dict[str, Any]
    decision: str  # ALLOW | PENDING_APPROVAL | BLOCKED | HUMAN_ONLY
    risk_level: str
    risk_score: float
    explanation: str
    decision_id: str
    simulated_execution: Optional[Dict[str, Any]] = None

class ConnectionRunResponse(BaseModel):
    task: str
    model_text: Optional[str] = None
    decisions: List[ToolDecisionDetail] = Field(default_factory=list)
    summary: str
