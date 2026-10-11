"""Tamper-evident ledger endpoints: explorer, cryptographic verification, and demo tampering."""
from typing import Any, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.schemas.ledger import (
    LedgerEntryResponse,
    LedgerListResponse,
    LedgerProofResponse,
    LedgerVerifyResponse,
    TamperSimulateRequest
)
from app.services import ledger_service
from app.api.deps import get_current_user

router = APIRouter(prefix="", tags=["Ledger"])

@router.get("/v1/ledger", response_model=LedgerListResponse)
def get_v1_ledger(
    q: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    agent_id: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
    from_date: Optional[str] = Query(default=None, alias="from"),
    to_date: Optional[str] = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user)
):
    """Retrieve chronologically chained ledger entries with search, filters, and total count."""
    entries, total = ledger_service.get_ledger_entries(
        limit=limit,
        offset=offset,
        q=q,
        event_type=event_type,
        agent_id=agent_id,
        risk_level=risk_level,
        from_date=from_date,
        to_date=to_date,
        return_total=True
    )
    return {
        "items": entries,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/v1/ledger/count")
@router.get("/ledger/count")
def get_ledger_count(user: dict = Depends(get_current_user)):
    """Lightweight endpoint returning the total count of ledger entries."""
    _, total = ledger_service.get_ledger_entries(limit=1, offset=0, return_total=True)
    return {"total": total, "count": total}

@router.get("/ledger")
def get_ledger(
    q: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    agent_id: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
    from_date: Optional[str] = Query(default=None, alias="from"),
    to_date: Optional[str] = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    include_total: bool = Query(default=False),
    user: dict = Depends(get_current_user)
):
    """Backwards-compatible endpoint returning List[LedgerEntryResponse], or LedgerListResponse if include_total=True."""
    entries, total = ledger_service.get_ledger_entries(
        limit=limit,
        offset=offset,
        q=q,
        event_type=event_type,
        agent_id=agent_id,
        risk_level=risk_level,
        from_date=from_date,
        to_date=to_date,
        return_total=True
    )
    if include_total:
        return {
            "items": entries,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    return entries

@router.get("/ledger/proof/{entry_id}", response_model=LedgerProofResponse)
@router.get("/v1/ledger/proof/{entry_id}", response_model=LedgerProofResponse)
def get_ledger_proof(entry_id: int, user: dict = Depends(get_current_user)):
    """
    Get cryptographic proof for an individual ledger entry,
    including link check against predecessor and recomputed SHA-256 hash.
    """
    proof = ledger_service.get_entry_proof(entry_id)
    if not proof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ledger entry #{entry_id} not found")
    return proof

@router.get("/ledger/verify", response_model=LedgerVerifyResponse)
@router.get("/v1/ledger/verify", response_model=LedgerVerifyResponse)
def verify_ledger(user: dict = Depends(get_current_user)):
    """
    Cryptographic verification endpoint.
    Recalculates every SHA-256 link in the entire ledger from genesis to tip.
    Returns valid: true/false and the exact index of any broken or tampered entry.
    """
    return ledger_service.verify_ledger_chain()

@router.post("/ledger/_tamper/{entry_id}")
@router.post("/v1/ledger/_tamper/{entry_id}")
def tamper_ledger_entry_dev(
    entry_id: int,
    req: Optional[TamperSimulateRequest] = None,
    user: dict = Depends(get_current_user)
):
    """
    DEV-ONLY SIMULATION:
    Directly alters a historical ledger record in the database without re-hashing.
    Allows proving that /ledger/verify immediately catches unauthorized tampering.
    """
    note = req.note if req and req.note else "Simulated unauthorized modification for audit testing"
    override = req.override_payload if req else None
    try:
        return ledger_service.tamper_entry(entry_id, new_payload=override, tamper_note=note)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
