"""Tests for Tamper-Evident Chained Ledger.
Verifies cryptographic chain integrity and tamper detection.
"""
from app.services.ledger_service import append_ledger_entry

def test_ledger_chain_is_valid_initially(client, admin_headers):
    """Initial seeded ledger must verify cleanly without any broken hashes."""
    res = client.get("/ledger/verify", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["total_entries"] >= 4
    assert data["broken_index"] is None
    assert data["broken_entry_id"] is None

def test_appending_entries_builds_valid_chain(client, admin_headers):
    """Appending multiple records continues the cryptographic hash chain seamlessly."""
    # Append entries
    append_ledger_entry(
        event_type="ACTION_EVALUATED",
        actor="support_agent_01",
        payload={"action": "issue_refund", "amount": 200, "status": "ALLOWED"}
    )
    append_ledger_entry(
        event_type="ACTION_EXECUTED",
        actor="support_agent_01",
        payload={"action": "issue_refund", "tx_id": "tx_999", "status": "SUCCESS"}
    )

    # Verify chain
    res = client.get("/ledger/verify", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["broken_index"] is None

    # Verify listing shows newest first
    list_res = client.get("/ledger?limit=10", headers=admin_headers)
    assert list_res.status_code == 200
    entries = list_res.json()
    assert len(entries) >= 6
    assert entries[0]["event_type"] == "ACTION_EXECUTED"
    assert entries[1]["event_type"] == "ACTION_EVALUATED"

def test_tampering_with_entry_is_detected(client, admin_headers):
    """Tampering with a historical entry via DEV endpoint causes /ledger/verify to fail."""
    # Ensure chain is initially valid
    initial_verify = client.get("/ledger/verify", headers=admin_headers).json()
    assert initial_verify["valid"] is True

    # Tamper with entry #2
    tamper_res = client.post("/ledger/_tamper/2", headers=admin_headers, json={"note": "Unauthorized modify test"})
    assert tamper_res.status_code == 200
    assert tamper_res.json()["tampered"] is True

    # Verification must now immediately fail and report entry #2
    verify_res = client.get("/ledger/verify", headers=admin_headers)
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["valid"] is False
    assert verify_data["broken_entry_id"] == 2
    assert "Tampering detected at entry ID 2" in verify_data["message"]
