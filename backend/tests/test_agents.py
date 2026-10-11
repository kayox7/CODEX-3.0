"""Tests for Agent Passports and Ledger audit synchronization.
Ensures creation, pause, resume update state and write tamper-evident ledger entries.
"""

def test_agent_lifecycle_and_ledger_recording(client, admin_headers):
    """
    Test agent lifecycle:
    1. Create an agent -> verify passport and AGENT_REGISTERED ledger entry
    2. Pause the agent  -> verify paused status and AGENT_PAUSED ledger entry
    3. Resume the agent -> verify active status and AGENT_RESUMED ledger entry
    4. Confirm ledger chain remains valid throughout
    """
    # 1. Fetch initial ledger entries
    initial_ledger = client.get("/ledger", headers=admin_headers).json()
    initial_count = len(initial_ledger)

    agent_id = "lifecycle_agent_99"
    create_payload = {
        "agent_id": agent_id,
        "name": "Lifecycle Governed Agent",
        "owner": "admin",
        "purpose": "Validating full governance lifecycle",
        "allowed_actions": ["issue_refund", "update_record"],
        "allowed_data_classes": ["public", "internal"],
        "max_amount": 5000.0,
        "status": "active"
    }

    # CREATE AGENT
    create_res = client.post("/agents", headers=admin_headers, json=create_payload)
    assert create_res.status_code == 201
    created_passport = create_res.json()
    assert created_passport["agent_id"] == agent_id
    assert created_passport["status"] == "active"
    assert created_passport["max_amount"] == 5000.0

    # Verify AGENT_REGISTERED in ledger
    ledger_after_create = client.get("/ledger", headers=admin_headers).json()
    assert len(ledger_after_create) == initial_count + 1
    newest_entry = ledger_after_create[0]
    assert newest_entry["event_type"] == "AGENT_REGISTERED"
    assert newest_entry["payload"]["agent_id"] == agent_id

    # PAUSE AGENT
    pause_res = client.post(
        f"/agents/{agent_id}/pause",
        headers=admin_headers,
        json={"reason": "Suspicious activity detected"}
    )
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "paused"

    # Verify agent passport is paused
    get_res = client.get(f"/agents/{agent_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "paused"

    # Verify AGENT_PAUSED in ledger
    ledger_after_pause = client.get("/ledger", headers=admin_headers).json()
    assert len(ledger_after_pause) == initial_count + 2
    pause_entry = ledger_after_pause[0]
    assert pause_entry["event_type"] == "AGENT_PAUSED"
    assert pause_entry["payload"]["agent_id"] == agent_id
    assert pause_entry["payload"]["reason"] == "Suspicious activity detected"

    # RESUME AGENT
    resume_res = client.post(
        f"/agents/{agent_id}/resume",
        headers=admin_headers,
        json={"reason": "Audit review passed"}
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "active"

    # Verify agent passport is active
    get_res = client.get(f"/agents/{agent_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "active"

    # Verify AGENT_RESUMED in ledger
    ledger_after_resume = client.get("/ledger", headers=admin_headers).json()
    assert len(ledger_after_resume) == initial_count + 3
    resume_entry = ledger_after_resume[0]
    assert resume_entry["event_type"] == "AGENT_RESUMED"
    assert resume_entry["payload"]["agent_id"] == agent_id
    assert resume_entry["payload"]["reason"] == "Audit review passed"

    # Verify entire cryptographic chain is valid
    verify_res = client.get("/ledger/verify", headers=admin_headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True
    assert verify_res.json()["total_entries"] == initial_count + 3
