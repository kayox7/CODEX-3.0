"""Tests for GET /v1/ledger filters, search, pagination, and proof endpoints."""
from app.services.ledger_service import append_ledger_entry

def test_v1_ledger_returns_total_and_items(client, admin_headers):
    """GET /v1/ledger returns paginated items and total count."""
    res = client.get("/v1/ledger?limit=10&offset=0", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    assert data["total"] >= len(data["items"])
    assert data["limit"] == 10
    assert data["offset"] == 0

def test_v1_ledger_filter_by_agent_id(client, admin_headers):
    """Filter ledger entries by agent_id."""
    # Append test record
    append_ledger_entry(
        event_type="ACTION_ALLOWED",
        actor="test_filter_agent_99",
        payload={"action": "test_filter_action", "amount": 100, "risk_level": "LOW"}
    )
    res = client.get("/v1/ledger?agent_id=test_filter_agent_99", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["actor"] == "test_filter_agent_99" or item["payload"].get("agent_id") == "test_filter_agent_99"

def test_v1_ledger_filter_by_risk_level(client, admin_headers):
    """Filter ledger entries by risk_level."""
    append_ledger_entry(
        event_type="ACTION_BLOCKED",
        actor="support_agent_01",
        payload={"action": "test_high_risk", "risk_level": "RESTRICTED", "amount": 50000}
    )
    res = client.get("/v1/ledger?risk_level=RESTRICTED", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["payload"].get("risk_level") == "RESTRICTED"

def test_v1_ledger_filter_by_event_type(client, admin_headers):
    """Filter ledger entries by event_type or decision category."""
    res = client.get("/v1/ledger?event_type=ALLOW", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert isinstance(data["total"], int)

def test_v1_ledger_search_query(client, admin_headers):
    """Search ledger entries across actor, event_type, and payload."""
    append_ledger_entry(
        event_type="ACTION_ALLOWED",
        actor="support_agent_01",
        payload={"action": "unique_needle_action_xyz", "amount": 42}
    )
    res = client.get("/v1/ledger?q=unique_needle_action_xyz", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any("unique_needle_action_xyz" in str(item["payload"]) for item in data["items"])

def test_ledger_proof_endpoint(client, admin_headers):
    """Check cryptographic link proof for an individual entry."""
    # Genesis entry ID 1
    res = client.get("/v1/ledger/proof/1", headers=admin_headers)
    assert res.status_code == 200
    proof = res.json()
    assert proof["id"] == 1
    assert proof["is_valid"] is True
    assert proof["is_link_valid"] is True
    assert proof["is_hash_valid"] is True
    assert "prev_hash" in proof
    assert "hash" in proof

def test_ledger_proof_404_for_missing(client, admin_headers):
    """Check 404 for non-existent entry ID."""
    res = client.get("/v1/ledger/proof/999999", headers=admin_headers)
    assert res.status_code == 404
