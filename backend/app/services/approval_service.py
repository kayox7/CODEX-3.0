"""Human Approval and Multi-tier SLA Escalation Service.
Enforces separation of duties, role-tiered review authority, and fail-closed SLA timeouts.
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from app.config import settings
from app.db import get_connection
from app.services.agent_service import get_agent_by_id
from app.services.ledger_service import append_ledger_entry

def get_approvals(
    status_filter: Optional[str] = None,
    agent_id: Optional[str] = None,
    mine_only: bool = False,
    current_user: Optional[Dict[str, Any]] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Retrieve approval requests with optional filters."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT id, decision_id, agent_id, action, params, data_class, amount, records_affected,
           reversibility, risk_score, risk_level, risk_breakdown, evidence_pack, status,
           escalation_level, created_at, sla_deadline, resolved_at, resolved_by,
           resolution_reason, ledger_hash
    FROM approval_requests
    """
    conditions = []
    params = []

    if status_filter:
        s_clean = status_filter.strip().upper()
        if s_clean in ("PENDING", "PENDING_APPROVAL"):
            conditions.append("status = 'PENDING'")
        else:
            conditions.append("status = ?")
            params.append(status_filter)
    if agent_id:
        conditions.append("agent_id = ?")
        params.append(agent_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    approvals = []
    for r in rows:
        appr = {
            "id": r["id"],
            "decision_id": r["decision_id"],
            "agent_id": r["agent_id"],
            "action": r["action"],
            "params": json.loads(r["params"]),
            "data_class": r["data_class"],
            "amount": r["amount"],
            "records_affected": r["records_affected"],
            "reversibility": r["reversibility"],
            "risk_score": r["risk_score"],
            "risk_level": r["risk_level"],
            "risk_breakdown": json.loads(r["risk_breakdown"]),
            "evidence_pack": json.loads(r["evidence_pack"]),
            "status": r["status"],
            "escalation_level": r["escalation_level"],
            "created_at": r["created_at"],
            "sla_deadline": r["sla_deadline"],
            "resolved_at": r["resolved_at"],
            "resolved_by": r["resolved_by"],
            "resolution_reason": r["resolution_reason"],
            "ledger_hash": r["ledger_hash"]
        }

        # Filter by 'mine' (requests where current_user is eligible to approve)
        if mine_only and current_user:
            # Separation of duties: User cannot approve actions for agents they own
            agent = get_agent_by_id(appr["agent_id"])
            if agent and agent["owner"] == current_user["username"]:
                continue
            # Role matching for escalation level
            user_role = current_user["role"]
            level = appr["escalation_level"]
            if level == "RISK_LEAD" and user_role not in ("risk_lead", "executive", "admin"):
                continue
            if level == "EXECUTIVE" and user_role not in ("executive", "admin"):
                continue

        approvals.append(appr)

    return approvals

def get_approval_by_id(approval_id: int) -> Optional[Dict[str, Any]]:
    """Get single approval request by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, decision_id, agent_id, action, params, data_class, amount, records_affected,
           reversibility, risk_score, risk_level, risk_breakdown, evidence_pack, status,
           escalation_level, created_at, sla_deadline, resolved_at, resolved_by,
           resolution_reason, ledger_hash
    FROM approval_requests WHERE id = ?
    """, (approval_id,))
    r = cursor.fetchone()
    conn.close()

    if not r:
        return None

    return {
        "id": r["id"],
        "decision_id": r["decision_id"],
        "agent_id": r["agent_id"],
        "action": r["action"],
        "params": json.loads(r["params"]),
        "data_class": r["data_class"],
        "amount": r["amount"],
        "records_affected": r["records_affected"],
        "reversibility": r["reversibility"],
        "risk_score": r["risk_score"],
        "risk_level": r["risk_level"],
        "risk_breakdown": json.loads(r["risk_breakdown"]),
        "evidence_pack": json.loads(r["evidence_pack"]),
        "status": r["status"],
        "escalation_level": r["escalation_level"],
        "created_at": r["created_at"],
        "sla_deadline": r["sla_deadline"],
        "resolved_at": r["resolved_at"],
        "resolved_by": r["resolved_by"],
        "resolution_reason": r["resolution_reason"],
        "ledger_hash": r["ledger_hash"]
    }

def approve_request(
    approval_id: int,
    user: Dict[str, Any],
    reason: Optional[str] = "Authorized by human reviewer"
) -> Dict[str, Any]:
    """
    Approve a pending request.
    Enforces Separation of Duties: Approver cannot approve their own agent's actions.
    Enforces Role Authority: Checks required role for current escalation level.
    """
    approval = get_approval_by_id(approval_id)
    if not approval:
        raise ValueError(f"Approval request {approval_id} not found")

    if approval["status"] != "PENDING":
        raise ValueError(f"Approval request {approval_id} is already resolved ({approval['status']})")

    # 1. SEPARATION OF DUTIES ENFORCEMENT
    agent = get_agent_by_id(approval["agent_id"])
    if agent and agent["owner"] == user["username"]:
        raise PermissionError(
            f"Separation of duties violation: User '{user['username']}' owns agent '{approval['agent_id']}' and cannot approve its actions."
        )

    # 2. ROLE AUTHORITY ENFORCEMENT
    user_role = user.get("role")
    level = approval["escalation_level"]
    if level == "RISK_LEAD" and user_role not in ("risk_lead", "executive", "admin"):
        raise PermissionError(f"Action escalated to RISK_LEAD requires risk_lead or higher role. User has '{user_role}'.")
    if level == "EXECUTIVE" and user_role not in ("executive", "admin"):
        raise PermissionError(f"Action escalated to EXECUTIVE requires executive or higher role. User has '{user_role}'.")

    # 3. Update DB
    now = datetime.utcnow().isoformat() + "Z"
    reason_clean = reason or "Authorized by human reviewer"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE approval_requests
    SET status = 'APPROVED', resolved_at = ?, resolved_by = ?, resolution_reason = ?
    WHERE id = ?
    """, (now, user["username"], reason_clean, approval_id))
    conn.commit()
    conn.close()

    # 4. Record ACTION_APPROVED in Ledger
    ledger_record = append_ledger_entry(
        event_type="ACTION_APPROVED",
        actor=user["username"],
        payload={
            "approval_id": approval_id,
            "decision_id": approval["decision_id"],
            "agent_id": approval["agent_id"],
            "action": approval["action"],
            "amount": approval["amount"],
            "approved_by": user["username"],
            "escalation_level": level,
            "reason": reason_clean
        }
    )

    # Link hash
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE approval_requests SET ledger_hash = ? WHERE id = ?", (ledger_record["hash"], approval_id))
    conn.commit()
    conn.close()

    return get_approval_by_id(approval_id)

def reject_request(
    approval_id: int,
    user: Dict[str, Any],
    reason: str
) -> Dict[str, Any]:
    """
    Reject a pending request with mandatory reason.
    """
    if not reason or not reason.strip():
        raise ValueError("Rejection reason is required")

    approval = get_approval_by_id(approval_id)
    if not approval:
        raise ValueError(f"Approval request {approval_id} not found")

    if approval["status"] != "PENDING":
        raise ValueError(f"Approval request {approval_id} is already resolved ({approval['status']})")

    now = datetime.utcnow().isoformat() + "Z"
    reason_clean = reason.strip()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE approval_requests
    SET status = 'REJECTED', resolved_at = ?, resolved_by = ?, resolution_reason = ?
    WHERE id = ?
    """, (now, user["username"], reason_clean, approval_id))
    conn.commit()
    conn.close()

    # Record ACTION_REJECTED in Ledger
    ledger_record = append_ledger_entry(
        event_type="ACTION_REJECTED",
        actor=user["username"],
        payload={
            "approval_id": approval_id,
            "decision_id": approval["decision_id"],
            "agent_id": approval["agent_id"],
            "action": approval["action"],
            "amount": approval["amount"],
            "rejected_by": user["username"],
            "reason": reason_clean
        }
    )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE approval_requests SET ledger_hash = ? WHERE id = ?", (ledger_record["hash"], approval_id))
    conn.commit()
    conn.close()

    return get_approval_by_id(approval_id)

def check_and_escalate_approvals(sla_seconds: Optional[int] = None) -> Dict[str, Any]:
    """
    Scan pending approval requests where SLA has expired.
    Chain: APPROVER -> RISK_LEAD -> EXECUTIVE -> TIMED_OUT (fail-closed BLOCKED).
    """
    effective_sla = sla_seconds if sla_seconds is not None else settings.APPROVAL_SLA_SECONDS
    now_dt = datetime.utcnow()
    now_iso = now_dt.isoformat() + "Z"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, decision_id, agent_id, action, amount, escalation_level, sla_deadline
    FROM approval_requests
    WHERE status = 'PENDING' AND sla_deadline <= ?
    """, (now_iso,))
    rows = cursor.fetchall()
    conn.close()

    escalated = []
    timed_out = []

    for r in rows:
        appr_id = r["id"]
        current_level = r["escalation_level"]
        decision_id = r["decision_id"]
        agent_id = r["agent_id"]
        action = r["action"]

        if current_level == "APPROVER":
            next_level = "RISK_LEAD"
            new_deadline = (now_dt + timedelta(seconds=effective_sla)).isoformat() + "Z"

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE approval_requests
            SET escalation_level = ?, sla_deadline = ?
            WHERE id = ?
            """, (next_level, new_deadline, appr_id))
            conn.commit()
            conn.close()

            ledger_rec = append_ledger_entry(
                event_type="APPROVAL_ESCALATED",
                actor="SLA_MONITOR",
                payload={
                    "approval_id": appr_id,
                    "decision_id": decision_id,
                    "agent_id": agent_id,
                    "action": action,
                    "from_level": current_level,
                    "to_level": next_level,
                    "reason": "SLA timeout at APPROVER tier"
                }
            )
            escalated.append({"id": appr_id, "from": current_level, "to": next_level})

        elif current_level == "RISK_LEAD":
            next_level = "EXECUTIVE"
            new_deadline = (now_dt + timedelta(seconds=effective_sla)).isoformat() + "Z"

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE approval_requests
            SET escalation_level = ?, sla_deadline = ?
            WHERE id = ?
            """, (next_level, new_deadline, appr_id))
            conn.commit()
            conn.close()

            ledger_rec = append_ledger_entry(
                event_type="APPROVAL_ESCALATED",
                actor="SLA_MONITOR",
                payload={
                    "approval_id": appr_id,
                    "decision_id": decision_id,
                    "agent_id": agent_id,
                    "action": action,
                    "from_level": current_level,
                    "to_level": next_level,
                    "reason": "SLA timeout at RISK_LEAD tier"
                }
            )
            escalated.append({"id": appr_id, "from": current_level, "to": next_level})

        elif current_level == "EXECUTIVE":
            # Executive SLA expired -> Action permanently blocked (Fail-Closed)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE approval_requests
            SET status = 'TIMED_OUT', resolved_at = ?, resolved_by = 'SLA_MONITOR',
                resolution_reason = 'Fail-Closed: Executive SLA expired without human decision'
            WHERE id = ?
            """, (now_iso, appr_id))
            conn.commit()
            conn.close()

            ledger_rec = append_ledger_entry(
                event_type="APPROVAL_TIMEOUT",
                actor="SLA_MONITOR",
                payload={
                    "approval_id": appr_id,
                    "decision_id": decision_id,
                    "agent_id": agent_id,
                    "action": action,
                    "status": "TIMED_OUT",
                    "reason": "Fail-Closed: Action permanently blocked after executive timeout"
                }
            )
            timed_out.append({"id": appr_id, "decision_id": decision_id})

    return {
        "checked_at": now_iso,
        "escalated_count": len(escalated),
        "timed_out_count": len(timed_out),
        "escalated": escalated,
        "timed_out": timed_out
    }
