from typing import List, Optional
from pydantic import BaseModel, Field

class AgentCreateRequest(BaseModel):
    name: str
    purpose: str
    agent_id: Optional[str] = None
    owner: Optional[str] = None
    allowed_actions: List[str] = Field(default_factory=list)
    allowed_data_classes: List[str] = Field(default_factory=list)
    max_amount: float = 0.0
    status: str = "active"
    custom_api_key: Optional[str] = None

class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    purpose: Optional[str] = None
    allowed_actions: Optional[List[str]] = None
    allowed_data_classes: Optional[List[str]] = None
    max_amount: Optional[float] = None
    status: Optional[str] = None

class AgentPassportResponse(BaseModel):
    id: Optional[int] = None
    agent_id: str
    name: str
    owner: str
    purpose: str
    allowed_actions: List[str]
    allowed_data_classes: List[str]
    max_amount: float
    status: str
    api_key_prefix: Optional[str] = None
    api_key: Optional[str] = None
    created_at: str
    updated_at: str

class AgentStatusActionRequest(BaseModel):
    reason: Optional[str] = "Manual state change via console"
