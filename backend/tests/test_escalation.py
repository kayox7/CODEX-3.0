"""Tests for Multi-Tier SLA Escalation and Fail-Closed Timeouts.
Validates APPROVER -> RISK_LEAD -> EXECUTIVE -> TIMED_OUT (Fail-Closed).
"""
from datetime import datetime, timedelta
from app.db import get_connection
from app.services.approval_service import check_and_escalate_approvals

def test_multi_tier_sla_escalation_flow(client, admin_headers):
    """
    Test complete escalation lifecycle:
    1. Request starts at APPROVER level
    2. 1st SLA timeout: Escalates to RISK_LEAD
    3. 2nd SLA timeout: Escalates to EXECUTIVE
    4. 3rd SLA timeout: Executive SLA expires -> Status becomes TIMED_OUT (Fail-Closed)
    """
    # 1. Create a request requiring approval
    res = client.post("/v1/actions/request", json={
        "agent_id": "support_agent_01",
        "action": "issue_refund",
        "amount": 80000.0,
        "records_affected": 2,
        "data_class": "confidential",
        "reversibility": "partially"
    })
    assert res.status_code == 200
    decision_id = res.json()["decision_id"]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, escalation_level FROM approval_requests WHERE decision_id = ?", (decision_id,))
    row = cursor.fetchone()
    approval_id = row["id"]
    assert row["escalation_level"] == "APPROVER"
    assert row["status"] == "PENDING"

    # Helper function to backdate deadline to the past
    def backdate_deadline():
        past = (datetime.utcnow() - timedelta(seconds=10)).isoformat() + "Z"
        c = get_connection()
        cur = c.cursor()
        cur.execute("UPDATE approval_requests SET sla_deadline = ? WHERE id = ?", (past, approval_id))
        c.commit()
        c.close()

    # --- STEP 1: First SLA Expiry -> Escalate to RISK_LEAD ---
    backdate_deadline()
    esc_result1 = check_and_escalate_approvals(sla_seconds=2)
    assert esc_result1["escalated_count"] >= 1

    cursor.execute("SELECT status, escalation_level FROM approval_requests WHERE id = ?", (approval_id,))
    row1 = cursor.fetchone()
    assert row1["escalation_level"] == "RISK_LEAD"
    assert row1["status"] == "PENDING"

    # --- STEP 2: Second SLA Expiry -> Escalate to EXECUTIVE ---
    backdate_deadline()
    esc_result2 = check_and_escalate_approvals(sla_seconds=2)
    assert esc_result2["escalated_count"] >= 1

    cursor.execute("SELECT status, escalation_level FROM approval_requests WHERE id = ?", (approval_id,))
    row2 = cursor.fetchone()
    assert row2["escalation_level"] == "EXECUTIVE"
    assert row2["status"] == "PENDING"

    # --- STEP 3: Third SLA Expiry -> EXECUTIVE Timeout -> Fail-Closed BLOCKED ---
    backdate_deadline()
    esc_result3 = check_and_escalate_approvals(sla_seconds=2)
    assert esc_result3["timed_out_count"] >= 1

    cursor.execute("SELECT status, escalation_level, resolution_reason FROM approval_requests WHERE id = ?", (approval_id,))
    row3 = cursor.fetchone()
    conn.close()

    assert row3["status"] == "TIMED_OUT"
    assert "Executive SLA expired" in row3["resolution_reason"]

    # Verify decision endpoint now reports BLOCKED
    poll_res = client.get(f"/v1/actions/decision/{decision_id}")
    assert poll_res.status_code == 200
    assert poll_res.json()["decision"] == "BLOCKED"

def test_escalation_endpoint_via_api(client, admin_headers):
    """API endpoint /approvals/check-escalations triggers background check on demand."""
    res = client.post("/approvals/check-escalations?sla_seconds=5", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "escalated_count" in data
    assert "timed_out_count" in data
