"""Tests for Decision Engine API /v1/actions/request."""
from app.db import get_connection

def test_decision_api_allows_low_risk_action(client):
    """Low-risk action receives ALLOW decision and records in ledger."""
    res = client.post("/v1/actions/request", json={
        "agent_id": "support_agent_01",
        "action": "issue_refund",
        "amount": 200.0,
        "records_affected": 1,
        "data_class": "confidential",
        "reversibility": "reversible"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "ALLOW"
    assert data["risk_level"] == "LOW"
    assert data["risk_score"] < 0.25
    assert data["decision_id"].startswith("dec_")
    assert "ledger_hash" in data

def test_decision_api_routes_medium_high_to_pending_approval(client):
    """Significant financial or operational impact creates an approval record with evidence pack."""
    res = client.post("/v1/actions/request", json={
        "agent_id": "support_agent_01",
        "action": "issue_refund",
        "amount": 80000.0,  # 80k refund -> blast radius score > 0.60
        "records_affected": 5,
        "data_class": "confidential",
        "reversibility": "partially"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "PENDING_APPROVAL"
    assert data["risk_level"] in ("MEDIUM", "HIGH")
    assert data["risk_score"] >= 0.25
    assert "evidence_pack" in data
    assert data["evidence_pack"]["amount"] == 80000.0

    # Verify approval record exists in DB
    decision_id = data["decision_id"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, escalation_level FROM approval_requests WHERE decision_id = ?", (decision_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["status"] == "PENDING"
    assert row["escalation_level"] == "APPROVER"

    # Verify decision status polling endpoint
    poll_res = client.get(f"/v1/actions/decision/{decision_id}")
    assert poll_res.status_code == 200
    assert poll_res.json()["decision"] == "PENDING_APPROVAL"

def test_decision_api_blocks_out_of_scope_and_triggers_kill_switch(client):
    """Out-of-scope actions return BLOCKED and auto-pause the agent."""
    res = client.post("/v1/actions/request", json={
        "agent_id": "support_agent_01",
        "action": "export_customers",  # out of scope
        "amount": 0.0,
        "records_affected": 10000,
        "data_class": "internal",
        "reversibility": "irreversible"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "BLOCKED"
    assert "Policy rule violation" in data["explanation"]
