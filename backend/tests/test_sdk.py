"""Tests for WARDEN Python SDK and @warden.guard decorator.
Verifies interceptor execution, pre-execution blockages, and fail-closed safety.
"""
import pytest
# pyrefly: ignore [missing-import]
from warden_sdk import Warden, WardenBlocked

def test_sdk_allows_and_executes_safe_action(client):
    """Guarded tool with LOW risk executes normally and returns its return value."""
    warden = Warden(
        api_url="http://testserver",
        api_key="wrd_demo_support_key_123",
        agent_id="support_agent_01",
        http_client=client
    )

    executed = False

    @warden.guard(action="issue_refund", data_class="confidential", reversibility="reversible")
    def process_refund(customer_id: str, amount: float):
        nonlocal executed
        executed = True
        return f"Refund of Rs {amount} processed for {customer_id}"

    result = process_refund("cust_101", 200.0)
    assert executed is True
    assert result == "Refund of Rs 200.0 processed for cust_101"

def test_sdk_blocks_policy_violating_action_before_execution(client):
    """Guarded tool with out-of-scope action is intercepted and blocked before invocation."""
    warden = Warden(
        api_url="http://testserver",
        api_key="wrd_demo_support_key_123",
        agent_id="support_agent_01",
        http_client=client
    )

    executed = False

    @warden.guard(action="export_customers", data_class="internal", reversibility="partially")
    def export_data():
        nonlocal executed
        executed = True
        return "DATA_EXPORTED"

    with pytest.raises(WardenBlocked) as exc_info:
        export_data()

    assert executed is False  # CRITICAL: Function must never have executed
    assert "Policy rule violation" in str(exc_info.value) or "blocked" in str(exc_info.value).lower()

def test_sdk_blocks_globally_restricted_action(client):
    """Dangerous actions like delete_database are blocked immediately (HUMAN_ONLY / BLOCKED)."""
    warden = Warden(
        api_url="http://testserver",
        api_key="wrd_demo_support_key_123",
        agent_id="support_agent_01",
        http_client=client
    )

    executed = False

    @warden.guard(action="delete_database", data_class="restricted", reversibility="irreversible")
    def wipe_db():
        nonlocal executed
        executed = True
        return "WIPED"

    with pytest.raises(WardenBlocked) as exc_info:
        wipe_db()

    assert executed is False
    assert "blocked" in str(exc_info.value).lower() or "restricted" in str(exc_info.value).lower()

def test_sdk_fail_closed_when_server_is_unreachable():
    """
    FAIL-CLOSED GUARANTEE:
    If WARDEN governance server is down, unreachable, or errors,
    the SDK must immediately block execution and raise WardenBlocked.
    """
    # Point to non-existent port
    warden_offline = Warden(
        api_url="http://127.0.0.1:59999",
        api_key="invalid_key",
        agent_id="support_agent_01",
        fail_closed=True
    )

    executed = False

    @warden_offline.guard(action="issue_refund", data_class="public", reversibility="reversible")
    def critical_enterprise_call():
        nonlocal executed
        executed = True
        return "EXECUTED"

    with pytest.raises(WardenBlocked) as exc_info:
        critical_enterprise_call()

    # The enterprise system function must NEVER execute
    assert executed is False
    assert "Fail-Closed" in str(exc_info.value) or "Governance unreachable" in str(exc_info.value)
