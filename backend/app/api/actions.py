"""Action pre-execution control endpoints intercepted by WARDEN SDK."""
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status
from app.db import get_connection
from app.schemas.action import ActionRequest, ActionDecisionResponse, ActionExecutionReport
from app.services import decision_service, agent_service, ledger_service

router = APIRouter(prefix="", tags=["Actions"])

@router.post("/v1/actions/request", response_model=ActionDecisionResponse)
@router.post("/actions/request", response_model=ActionDecisionResponse)
async def request_action_governance(
    req: ActionRequest,
    x_warden_api_key: Optional[str] = Header(default=None, alias="X-Warden-Api-Key")
):
    """
    Main pre-execution control checkpoint.
    Intercepted by WARDEN SDK before any AI agent invokes an enterprise tool or executes code.
    Returns: ALLOW | PENDING_APPROVAL | BLOCKED | HUMAN_ONLY.
    """
    # If API key header provided, optional verification against passport
    if x_warden_api_key:
        agent = agent_service.get_agent_by_id(req.agent_id)
        if agent and not agent_service.verify_agent_api_key(req.agent_id, x_warden_api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid WARDEN API key for agent '{req.agent_id}'"
            )

    return await decision_service.process_action_request(
        agent_id=req.agent_id,
        action=req.action,
        params=req.params,
        amount=req.amount,
        records_affected=req.records_affected,
        data_class=req.data_class,
        reversibility=req.reversibility
    )

@router.get("/v1/actions/decision/{decision_id}", response_model=ActionDecisionResponse)
@router.get("/actions/decision/{decision_id}", response_model=ActionDecisionResponse)
def get_action_decision_status(decision_id: str):
    """
    Check the current resolution status of a pending action decision.
    Used by SDK when polling for human approval.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT decision_id, agent_id, action, status, risk_score, risk_level,
           resolution_reason, ledger_hash
    FROM approval_requests WHERE decision_id = ?
    """, (decision_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Decision '{decision_id}' not found")

    status_str = row["status"]
    # Map approval status to decision
    if status_str == "APPROVED":
        decision = "ALLOW"
        explanation = f"Approved by human reviewer: {row['resolution_reason'] or 'Authorized'}"
    elif status_str in ("REJECTED", "TIMED_OUT"):
        decision = "BLOCKED"
        explanation = f"Denied by human reviewer or SLA expired ({status_str}): {row['resolution_reason'] or 'Not authorized'}"
    else:
        decision = "PENDING_APPROVAL"
        explanation = "Awaiting human review"

    return {
        "decision": decision,
        "decision_id": decision_id,
        "risk_score": row["risk_score"],
        "risk_level": row["risk_level"],
        "explanation": explanation,
        "ledger_hash": row["ledger_hash"]
    }

@router.post("/v1/actions/report")
@router.post("/actions/report")
def report_action_execution(report: ActionExecutionReport):
    """Report post-execution status back to ledger for audit traceability."""
    ledger_record = ledger_service.append_ledger_entry(
        event_type="ACTION_EXECUTED",
        actor=report.agent_id,
        payload={
            "decision_id": report.decision_id,
            "action": report.action,
            "status": report.status,
            "result_summary": report.result_summary
        }
    )
    return {"recorded": True, "hash": ledger_record["hash"]}
