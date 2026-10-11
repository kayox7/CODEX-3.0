"""Tests for Human Approvals Queue and Separation of Duties."""
from app.db import get_connection

def test_separation_of_duties_prevents_agent_owner_from_approving(client, admin_headers, approver_headers):
    """
    CRITICAL ENTERPRISE SECURITY RULE:
    An agent owner cannot approve their own agent's high-risk actions.
    - support_agent_01 is owned by 'admin'
    - 'admin' attempting to approve support_agent_01 action -> 403 FORBIDDEN
    - 'approver' (independent reviewer) approving support_agent_01 action -> 200 OK
    """
    # 1. Trigger high-risk refund request for support_agent_01 (owned by admin)
    action_res = client.post("/v1/actions/request", json={
        "agent_id": "support_agent_01",
        "action": "issue_refund",
        "amount": 75000.0,
        "records_affected": 2,
        "data_class": "confidential",
        "reversibility": "partially"
    })
    assert action_res.status_code == 200
    decision_data = action_res.json()
    assert decision_data["decision"] == "PENDING_APPROVAL"
    decision_id = decision_data["decision_id"]

    # 2. Get approval request ID
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM approval_requests WHERE decision_id = ?", (decision_id,))
    approval_id = cursor.fetchone()["id"]
    conn.close()

    # 3. Agent owner ('admin') attempts to approve their own agent's action -> 403 Forbidden
    owner_approve_res = client.post(
        f"/approvals/{approval_id}/approve",
        headers=admin_headers,
        json={"reason": "I created this agent, approving it myself"}
    )
    assert owner_approve_res.status_code == 403
    assert "Separation of duties violation" in owner_approve_res.json()["detail"]

    # 4. Independent reviewer ('approver') approves -> 200 OK
    independent_approve_res = client.post(
        f"/approvals/{approval_id}/approve",
        headers=approver_headers,
        json={"reason": "Legitimate customer refund verified against ticket #4412"}
    )
    assert independent_approve_res.status_code == 200
    approved_data = independent_approve_res.json()
    assert approved_data["status"] == "APPROVED"
    assert approved_data["resolved_by"] == "approver"
    assert "ticket #4412" in approved_data["resolution_reason"]

def test_approver_cannot_approve_their_own_agent(client, approver_headers, admin_headers):
    """
    Data sync agent 02 is owned by 'approver'.
    'approver' cannot approve its actions; 'admin' can.
    """
    # 1. Trigger high-risk action for data_sync_agent_02 (owned by approver)
    action_res = client.post("/v1/actions/request", json={
        "agent_id": "data_sync_agent_02",
        "action": "sync_records",
        "amount": 0.0,
        "records_affected": 8000,  # 8000 records -> medium risk
        "data_class": "internal",
        "reversibility": "partially"
    })
    assert action_res.status_code == 200
    decision_data = action_res.json()
    assert decision_data["decision"] == "PENDING_APPROVAL"
    decision_id = decision_data["decision_id"]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM approval_requests WHERE decision_id = ?", (decision_id,))
    approval_id = cursor.fetchone()["id"]
    conn.close()

    # 2. 'approver' attempts to approve data_sync_agent_02 -> 403 Forbidden
    owner_approve_res = client.post(
        f"/approvals/{approval_id}/approve",
        headers=approver_headers,
        json={"reason": "Self-approval attempt"}
    )
    assert owner_approve_res.status_code == 403
    assert "Separation of duties violation" in owner_approve_res.json()["detail"]

    # 3. Independent user 'admin' approves -> 200 OK
    admin_approve_res = client.post(
        f"/approvals/{approval_id}/approve",
        headers=admin_headers,
        json={"reason": "Independent sync validation"}
    )
    assert admin_approve_res.status_code == 200
    assert admin_approve_res.json()["status"] == "APPROVED"

def test_reject_approval_requires_reason(client, approver_headers):
    """Rejection requires explicit justification reason and writes ACTION_REJECTED to ledger."""
    action_res = client.post("/v1/actions/request", json={
        "agent_id": "support_agent_01",
        "action": "issue_refund",
        "amount": 50000.0,
        "records_affected": 1,
        "data_class": "confidential",
        "reversibility": "partially"
    })
    decision_id = action_res.json()["decision_id"]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM approval_requests WHERE decision_id = ?", (decision_id,))
    approval_id = cursor.fetchone()["id"]
    conn.close()

    # 1. Reject without reason -> 422 Unprocessable (Pydantic validation) or 400
    bad_reject = client.post(f"/approvals/{approval_id}/reject", headers=approver_headers, json={"reason": ""})
    assert bad_reject.status_code in (400, 422)

    # 2. Reject with valid reason -> 200 OK
    good_reject = client.post(
        f"/approvals/{approval_id}/reject",
        headers=approver_headers,
        json={"reason": "Suspected fraudulent account pattern"}
    )
    assert good_reject.status_code == 200
    data = good_reject.json()
    assert data["status"] == "REJECTED"
    assert data["resolved_by"] == "approver"
    assert "Suspected fraudulent" in data["resolution_reason"]

    # 3. Decision polling endpoint reflects rejection as BLOCKED
    poll_res = client.get(f"/v1/actions/decision/{decision_id}")
    assert poll_res.status_code == 200
    assert poll_res.json()["decision"] == "BLOCKED"
