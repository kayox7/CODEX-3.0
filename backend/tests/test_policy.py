"""Tests for WARDEN Policy Engine and Python Fallback Evaluator.
Verifies permission scoping, budget caps, restricted actions, and auto-kill switch.
"""
from app.services.policy_service import evaluate_python_rules
from app.services.agent_service import get_agent_by_id

def test_policy_allows_valid_in_scope_request():
    """Agent active with valid action, permitted data class, and amount <= cap is allowed."""
    input_data = {
        "agent": {
            "agent_id": "support_agent_01",
            "status": "active",
            "allowed_actions": ["issue_refund", "update_record"],
            "allowed_data_classes": ["public", "internal", "confidential"],
            "max_amount": 100000.0
        },
        "action": "issue_refund",
        "data_class": "confidential",
        "amount": 500.0
    }
    result = evaluate_python_rules(input_data)
    assert result["allow"] is True
    assert len(result["violations"]) == 0

def test_policy_denies_out_of_scope_action():
    """Action outside agent allowed_actions is denied with clear violation explanation."""
    input_data = {
        "agent": {
            "agent_id": "support_agent_01",
            "status": "active",
            "allowed_actions": ["issue_refund", "update_record"],
            "allowed_data_classes": ["public", "internal"],
            "max_amount": 100000.0
        },
        "action": "export_customers",  # out of scope
        "data_class": "internal",
        "amount": 0.0
    }
    result = evaluate_python_rules(input_data)
    assert result["allow"] is False
    assert any("not in agent allowed scope" in v for v in result["violations"])

def test_policy_denies_exceeded_data_class():
    """Data classification exceeding passport is denied."""
    input_data = {
        "agent": {
            "agent_id": "data_sync_agent_02",
            "status": "active",
            "allowed_actions": ["sync_records"],
            "allowed_data_classes": ["public", "internal"],
            "max_amount": 0.0
        },
        "action": "sync_records",
        "data_class": "confidential",  # not in allowed
        "amount": 0.0
    }
    result = evaluate_python_rules(input_data)
    assert result["allow"] is False
    assert any("exceeds agent allowed data classes" in v for v in result["violations"])

def test_policy_denies_amount_exceeding_max_amount():
    """Requested amount above agent max_amount is denied."""
    input_data = {
        "agent": {
            "agent_id": "finance_bot_03",
            "status": "active",
            "allowed_actions": ["vendor_payout"],
            "allowed_data_classes": ["internal", "confidential"],
            "max_amount": 25000.0
        },
        "action": "vendor_payout",
        "data_class": "internal",
        "amount": 30000.0  # exceeds 25,000
    }
    result = evaluate_python_rules(input_data)
    assert result["allow"] is False
    assert any("exceeds agent maximum limit" in v for v in result["violations"])

def test_policy_denies_paused_agent():
    """Paused or revoked agent cannot execute any action."""
    input_data = {
        "agent": {
            "agent_id": "support_agent_01",
            "status": "paused",
            "allowed_actions": ["issue_refund"],
            "allowed_data_classes": ["public"],
            "max_amount": 100000.0
        },
        "action": "issue_refund",
        "data_class": "public",
        "amount": 10.0
    }
    result = evaluate_python_rules(input_data)
    assert result["allow"] is False
    assert any("must be 'active'" in v for v in result["violations"])

def test_policy_denies_restricted_actions():
    """Dangerous actions (e.g., delete_database) are permanently denied to AI agents."""
    input_data = {
        "agent": {
            "agent_id": "admin_agent",
            "status": "active",
            "allowed_actions": ["delete_database"],
            "allowed_data_classes": ["restricted"],
            "max_amount": 1000000.0
        },
        "action": "delete_database",
        "data_class": "restricted",
        "amount": 0.0
    }
    result = evaluate_python_rules(input_data)
    assert result["allow"] is False
    assert any("globally restricted for AI agents" in v for v in result["violations"])

def test_policy_denial_triggers_kill_switch_in_api(client, admin_headers):
    """When an agent attempts a policy violation via the API, the Kill Switch pauses the agent."""
    agent_id = "support_agent_01"
    # Ensure agent is initially active
    agent = get_agent_by_id(agent_id)
    assert agent["status"] == "active"

    # Action outside allowed scope
    res = client.post("/v1/actions/request", json={
        "agent_id": agent_id,
        "action": "export_customers",  # not allowed
        "amount": 0.0,
        "records_affected": 10000,
        "data_class": "internal"
    })

    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "BLOCKED"
    assert "Policy rule violation" in data["explanation"]

    # Agent must now be auto-paused (Kill switch)
    updated_agent = get_agent_by_id(agent_id)
    assert updated_agent["status"] == "paused"
