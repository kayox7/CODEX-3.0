"""Tamper-evident ledger endpoints: explorer, cryptographic verification, and demo tampering."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.schemas.ledger import LedgerEntryResponse, LedgerVerifyResponse, TamperSimulateRequest
from app.services import ledger_service
from app.api.deps import get_current_user

router = APIRouter(prefix="", tags=["Ledger"])

@router.get("/ledger", response_model=List[LedgerEntryResponse])
@router.get("/v1/ledger", response_model=List[LedgerEntryResponse])
def get_ledger(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user)
):
    """Retrieve chronologically chained ledger entries (newest first)."""
    return ledger_service.get_ledger_entries(limit=limit, offset=offset)

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
