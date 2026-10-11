from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class LedgerEntryResponse(BaseModel):
    id: int
    timestamp: str
    event_type: str
    actor: str
    payload: Dict[str, Any]
    prev_hash: str
    hash: str

class LedgerListResponse(BaseModel):
    items: List[LedgerEntryResponse]
    total: int
    limit: int
    offset: int

class LedgerProofResponse(BaseModel):
    id: int
    timestamp: str
    event_type: str
    actor: str
    prev_hash: str
    hash: str
    expected_prev_hash: str
    is_link_valid: bool
    is_hash_valid: bool
    recomputed_hash: str
    is_valid: bool
    index: int
    total_entries: int
    message: str

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
