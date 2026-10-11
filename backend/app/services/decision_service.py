"""Decision Engine orchestrating Policy checks, Blast Radius scoring,
Kill Switch enforcement, Approvals creation, and Tamper-evident Ledger recording.
Fail-closed by design: Any unexpected error results in BLOCKED.
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from app.config import settings
from app.db import get_connection
from app.services.agent_service import get_agent_by_id, pause_agent
from app.services.policy_service import evaluate_policy
from app.services.risk_service import calculate_blast_radius
from app.services.ledger_service import append_ledger_entry, get_ledger_entries

async def process_action_request(
    agent_id: str,
    action: str,
    params: Optional[Dict[str, Any]] = None,
    amount: float = 0.0,
    records_affected: int = 0,
    data_class: str = "public",
    reversibility: str = "partially"
) -> Dict[str, Any]:
    """
    Evaluate action request through full WARDEN governance pipeline:
    1. Passport check
    2. Policy engine evaluation
    3. If FAIL: Auto-pause agent (Kill switch) + record BLOCKED in ledger
    4. If PASS: Blast radius risk calculation
    5. Route decision:
       - RESTRICTED -> HUMAN_ONLY
       - LOW -> ALLOW
       - MEDIUM/HIGH -> PENDING_APPROVAL (create approval with evidence pack)
    """
    decision_id = f"dec_{uuid.uuid4().hex[:12]}"
    params = params or {}
    safe_amount = float(amount or 0.0)
    safe_records = int(records_affected or 0)

    try:
        # 1. Fetch Agent Passport
        agent = get_agent_by_id(agent_id)
        if not agent:
            # Unregistered agent -> fail-closed
            explanation = f"Blocked: Agent '{agent_id}' is not registered in WARDEN registry"
            ledger_record = append_ledger_entry(
                event_type="ACTION_BLOCKED",
                actor=agent_id,
                payload={
                    "decision_id": decision_id,
                    "action": action,
                    "reason": explanation
                }
            )
            return {
                "decision": "BLOCKED",
                "decision_id": decision_id,
                "risk_score": 1.0,
                "risk_level": "BLOCKED",
                "explanation": explanation,
                "risk_breakdown": {},
                "ledger_hash": ledger_record["hash"]
            }

        # 2. Policy Engine evaluation (OPA or Python fallback)
        policy_result = await evaluate_policy(
            agent=agent,
            action=action,
            data_class=data_class,
            amount=safe_amount,
            params=params
        )

        # 3. Check for policy violations -> KILL SWITCH
        if not policy_result.get("allow"):
            violations = policy_result.get("violations", ["Policy rule violation"])
            violation_summary = "; ".join(violations)
            explanation = f"Blocked: Policy rule violation: {violation_summary}"

            # TRIGGER KILL SWITCH: Auto-pause agent
            try:
                pause_agent(
                    agent_id=agent_id,
                    reason=f"Kill switch triggered by policy violation: {violation_summary}",
                    actor="WARDEN_POLICY_ENGINE",
                    is_kill_switch=True
                )
            except Exception as pe:
                print(f"[WARDEN] Error pausing agent on kill switch: {pe}")

            # Record in Ledger
            ledger_record = append_ledger_entry(
                event_type="ACTION_BLOCKED",
                actor=agent_id,
                payload={
                    "decision_id": decision_id,
                    "action": action,
                    "amount": safe_amount,
                    "data_class": data_class,
                    "violations": violations,
                    "explanation": explanation,
                    "kill_switch_activated": True
                }
            )

            return {
                "decision": "BLOCKED",
                "decision_id": decision_id,
                "risk_score": 1.0,
                "risk_level": "BLOCKED",
                "explanation": explanation,
                "risk_breakdown": {"violations": violations},
                "ledger_hash": ledger_record["hash"]
            }

        # 4. Blast Radius Risk Scoring
        risk = calculate_blast_radius(
            amount=safe_amount,
            records_affected=safe_records,
            reversibility=reversibility,
            data_class=data_class,
            action=action
        )

        risk_score = risk["score"]
        risk_level = risk["risk_level"]

        # 5. Route based on risk level
        if risk_level == "RESTRICTED":
            explanation = f"Human execution required: {risk['explanation']}"
            ledger_record = append_ledger_entry(
                event_type="ACTION_BLOCKED",
                actor=agent_id,
                payload={
                    "decision_id": decision_id,
                    "action": action,
                    "data_class": data_class,
                    "risk_level": "RESTRICTED",
                    "explanation": explanation
                }
            )
            return {
                "decision": "HUMAN_ONLY",
                "decision_id": decision_id,
                "risk_score": risk_score,
                "risk_level": "RESTRICTED",
                "explanation": explanation,
                "risk_breakdown": risk,
                "ledger_hash": ledger_record["hash"]
            }

        if risk_level == "LOW":
            # ALLOW: Safe blast radius, executed pre-approved
            explanation = f"Approved automatically: {risk['explanation']}"
            ledger_record = append_ledger_entry(
                event_type="ACTION_ALLOWED",
                actor=agent_id,
                payload={
                    "decision_id": decision_id,
                    "action": action,
                    "amount": safe_amount,
                    "records_affected": safe_records,
                    "data_class": data_class,
                    "risk_score": risk_score,
                    "risk_level": "LOW",
                    "explanation": explanation
                }
            )
            return {
                "decision": "ALLOW",
                "decision_id": decision_id,
                "risk_score": risk_score,
                "risk_level": "LOW",
                "explanation": explanation,
                "risk_breakdown": risk,
                "ledger_hash": ledger_record["hash"]
            }

        # MEDIUM or HIGH: Requires Human Approval
        # Build evidence pack
        recent_entries = get_ledger_entries(limit=5)
        recent_history = [
            {"id": e["id"], "timestamp": e["timestamp"], "event": e["event_type"], "actor": e["actor"]}
            for e in recent_entries if e["actor"] == agent_id or e["event_type"].startswith("ACTION")
        ]

        evidence_pack = {
            "agent_passport": {
                "agent_id": agent["agent_id"],
                "name": agent["name"],
                "owner": agent["owner"],
                "status": agent["status"],
                "max_amount": agent["max_amount"],
                "allowed_actions": agent["allowed_actions"]
            },
            "action": action,
            "params": params,
            "data_class": data_class,
            "amount": safe_amount,
            "records_affected": safe_records,
            "reversibility": reversibility,
            "policy_evaluation": policy_result,
            "risk_breakdown": risk,
            "recent_agent_history": recent_history
        }

        # Create approval record
        now = datetime.utcnow()
        sla_seconds = settings.DEFAULT_APPROVAL_SLA_SECONDS
        sla_deadline = now + timedelta(seconds=sla_seconds)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO approval_requests (
            decision_id, agent_id, action, params, data_class, amount, records_affected,
            reversibility, risk_score, risk_level, risk_breakdown, evidence_pack,
            status, escalation_level, created_at, sla_deadline
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 'APPROVER', ?, ?)
        """, (
            decision_id, agent_id, action, json.dumps(params), data_class, safe_amount,
            safe_records, reversibility, risk_score, risk_level, json.dumps(risk),
            json.dumps(evidence_pack), now.isoformat() + "Z", sla_deadline.isoformat() + "Z"
        ))
        conn.commit()
        conn.close()

        # Record in ledger
        ledger_record = append_ledger_entry(
            event_type="APPROVAL_REQUESTED",
            actor=agent_id,
            payload={
                "decision_id": decision_id,
                "action": action,
                "amount": safe_amount,
                "records_affected": safe_records,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "sla_seconds": sla_seconds
            }
        )

        # Update approval with ledger hash
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE approval_requests SET ledger_hash = ? WHERE decision_id = ?", (ledger_record["hash"], decision_id))
        conn.commit()
        conn.close()

        explanation = f"Pending Human Approval: {risk['explanation']}. Awaiting reviewer sign-off."
        return {
            "decision": "PENDING_APPROVAL",
            "decision_id": decision_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "explanation": explanation,
            "risk_breakdown": risk,
            "evidence_pack": evidence_pack,
            "ledger_hash": ledger_record["hash"]
        }

    except Exception as e:
        # FAIL-CLOSED GUARANTEE
        fail_explanation = f"Blocked (Fail-Closed): Governance error during pre-execution evaluation: {str(e)}"
        try:
            append_ledger_entry(
                event_type="SYSTEM_ALERT",
                actor=agent_id,
                payload={"decision_id": decision_id, "error": str(e), "decision": "BLOCKED"}
            )
        except Exception:
            pass

        return {
            "decision": "BLOCKED",
            "decision_id": decision_id,
            "risk_score": 1.0,
            "risk_level": "BLOCKED",
            "explanation": fail_explanation,
            "risk_breakdown": {"error": str(e)}
        }
