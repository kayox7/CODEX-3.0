"""Tests for Agent Kill Switch (Pause/Resume) and Pre-Execution Enforcement."""
from app.services.agent_service import get_agent_by_id

def test_kill_switch_pauses_agent_and_blocks_all_subsequent_actions(client, admin_headers):
    """
    EMERGENCY KILL SWITCH TEST:
    1. Agent initially active and can execute low-risk actions
    2. Admin activates Kill Switch (POST /agents/{id}/pause)
    3. Any subsequent action request is immediately BLOCKED at pre-execution layer
    4. Admin resumes agent (POST /agents/{id}/resume)
    5. Agent can once again execute low-risk actions
    6. All transitions recorded in tamper-evident ledger
    """
    agent_id = "support_agent_01"

    # 1. Active agent executes safe action
    res1 = client.post("/v1/actions/request", json={
        "agent_id": agent_id,
        "action": "issue_refund",
        "amount": 100.0,
        "records_affected": 1,
        "data_class": "confidential",
        "reversibility": "reversible"
    })
    assert res1.status_code == 200
    assert res1.json()["decision"] == "ALLOW"

    # 2. TRIGGER EMERGENCY KILL SWITCH
    kill_res = client.post(
        f"/agents/{agent_id}/pause",
        headers=admin_headers,
        json={"reason": "Emergency security lockdown"}
    )
    assert kill_res.status_code == 200
    assert kill_res.json()["status"] == "paused"

    # Check passport
    passport = get_agent_by_id(agent_id)
    assert passport["status"] == "paused"

    # 3. Subsequent action attempt must be BLOCKED
    res2 = client.post("/v1/actions/request", json={
        "agent_id": agent_id,
        "action": "issue_refund",
        "amount": 50.0,
        "records_affected": 1,
        "data_class": "confidential",
        "reversibility": "reversible"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["decision"] == "BLOCKED"
    assert "must be 'active'" in data2["explanation"]

    # 4. RESUME AGENT
    resume_res = client.post(
        f"/agents/{agent_id}/resume",
        headers=admin_headers,
        json={"reason": "Incident resolved, safety verified"}
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "active"

    # 5. Safe action allowed again
    res3 = client.post("/v1/actions/request", json={
        "agent_id": agent_id,
        "action": "issue_refund",
        "amount": 150.0,
        "records_affected": 1,
        "data_class": "confidential",
        "reversibility": "reversible"
    })
    assert res3.status_code == 200
    assert res3.json()["decision"] == "ALLOW"

    # 6. Verify ledger integrity remains 100% valid
    verify_res = client.get("/ledger/verify", headers=admin_headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True
