from typing import Any, Dict, Optional
from pydantic import BaseModel

class LedgerEntryResponse(BaseModel):
    id: int
    timestamp: str
    event_type: str
    actor: str
    payload: Dict[str, Any]
    prev_hash: str
    hash: str

class LedgerVerifyResponse(BaseModel):
    valid: bool
    total_entries: int
    broken_index: Optional[int] = None
    broken_entry_id: Optional[int] = None
    reason: Optional[str] = None
    message: str

class TamperSimulateRequest(BaseModel):
    note: Optional[str] = "Simulated unauthorized modification for audit testing"
    override_payload: Optional[Dict[str, Any]] = None
