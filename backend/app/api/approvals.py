"""Human Approval queue and review endpoints.
Enforces RBAC, separation of duties, and SLA management.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.schemas.approval import (
    ApprovalResponse,
    ApproveRequest,
    RejectRequest,
    EscalationCheckResponse
)
from app.services import approval_service
from app.api.deps import get_current_user, require_roles

router = APIRouter(prefix="", tags=["Approvals"])

@router.get("/approvals", response_model=List[ApprovalResponse])
@router.get("/v1/approvals", response_model=List[ApprovalResponse])
def list_approvals(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    agent_id: Optional[str] = Query(default=None),
    mine: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user)
):
    """
    List governance approval queue.
    If mine=true, filters to requests eligible for current user review.
    """
    return approval_service.get_approvals(
        status_filter=status_filter,
        agent_id=agent_id,
        mine_only=mine,
        current_user=user,
        limit=limit,
        offset=offset
    )

@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
@router.get("/v1/approvals/{approval_id}", response_model=ApprovalResponse)
def get_approval(approval_id: int, user: dict = Depends(get_current_user)):
    """Retrieve full details and evidence pack for a single approval request."""
    appr = approval_service.get_approval_by_id(approval_id)
    if not appr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Approval request {approval_id} not found")
    return appr

@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
@router.post("/v1/approvals/{approval_id}/approve", response_model=ApprovalResponse)
def approve_action(
    approval_id: int,
    req: Optional[ApproveRequest] = None,
    user: dict = Depends(require_roles(["approver", "risk_lead", "executive", "admin"]))
):
    """
    Approve an agent action after reviewing the evidence pack.
    Enforces Separation of Duties: Users cannot approve their own agent's actions.
    """
    reason = req.reason if req and req.reason else "Authorized by human reviewer"
    try:
        return approval_service.approve_request(approval_id=approval_id, user=user, reason=reason)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
@router.post("/v1/approvals/{approval_id}/reject", response_model=ApprovalResponse)
def reject_action(
    approval_id: int,
    req: RejectRequest,
    user: dict = Depends(require_roles(["approver", "risk_lead", "executive", "admin"]))
):
    """
    Reject an agent action with mandatory justification reason.
    """
    try:
        return approval_service.reject_request(approval_id=approval_id, user=user, reason=req.reason)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.post("/approvals/check-escalations", response_model=EscalationCheckResponse)
@router.post("/v1/approvals/check-escalations", response_model=EscalationCheckResponse)
def trigger_escalation_check(
    sla_seconds: Optional[int] = Query(default=None),
    user: dict = Depends(get_current_user)
):
    """
    Trigger immediate scan of expired SLA approvals for escalation or fail-closed timeout.
    """
    return approval_service.check_and_escalate_approvals(sla_seconds=sla_seconds)
