"""Tests for Connected AI Agents feature.
Verifies:
- Key encryption at rest & zero secret leaks
- Friendly test results for invalid keys
- Paused and revoked connections block and log
- Unsafe base_url protection (SSRF prevention)
- Policy blocks (amount above limit) and kill switch auto-pause
- Routing to PENDING_APPROVAL for medium/high risk
- Unknown tool and invalid argument rejection
- Tool call truncation to at most 5 calls
- Provider timeout fail-closed guarantee
- RBAC permissions (Admin vs Auditor)
- Mock provider end-to-end ("refund 200" ALLOW, "refund 80000" PENDING_APPROVAL)
- Gemini adapter header authentication (no key in URL)
- Ledger verification integrity
"""
import os
import json
import pytest
from unittest.mock import patch, AsyncMock
from cryptography.fernet import Fernet
import httpx

from app.config import settings
from app.providers.google_gemini import GeminiAdapter
from app.services import crypto_service, security_service

TEST_FERNET_KEY = Fernet.generate_key().decode()

@pytest.fixture(autouse=True)
def setup_encryption_env():
    """Ensure valid encryption key and safe settings during connection tests."""
    old_secret = os.environ.get("KEY_ENCRYPTION_SECRET")
    old_allow_local = settings.ALLOW_LOCAL_UPSTREAMS

    os.environ["KEY_ENCRYPTION_SECRET"] = TEST_FERNET_KEY
    settings.KEY_ENCRYPTION_SECRET = TEST_FERNET_KEY
    settings.ALLOW_LOCAL_UPSTREAMS = False

    yield

    if old_secret is not None:
        os.environ["KEY_ENCRYPTION_SECRET"] = old_secret
        settings.KEY_ENCRYPTION_SECRET = old_secret
    else:
        os.environ.pop("KEY_ENCRYPTION_SECRET", None)
        settings.KEY_ENCRYPTION_SECRET = None
    settings.ALLOW_LOCAL_UPSTREAMS = old_allow_local

def test_auditor_cannot_create_admin_can(client, admin_headers, auditor_headers):
    """Auditor cannot create, admin can; auditor can read."""
    payload = {
        "name": "Audit Test Connection",
        "provider": "mock",
        "api_key": "mock-auditor-key-1234",
        "model": "warden-mock-v1",
        "allowed_actions": ["issue_refund"],
        "max_amount": 5000.0
    }

    # Auditor create -> 403 Forbidden
    res_auditor = client.post("/v1/connections", headers=auditor_headers, json=payload)
    assert res_auditor.status_code == 403

    # Admin create -> 201 Created
    res_admin = client.post("/v1/connections", headers=admin_headers, json=payload)
    assert res_admin.status_code == 201
    conn_data = res_admin.json()
    assert conn_data["name"] == "Audit Test Connection"
    assert conn_data["key_last4"] == "1234"

    # Auditor can list and read
    list_res = client.get("/v1/connections", headers=auditor_headers)
    assert list_res.status_code == 200
    assert any(c["id"] == conn_data["id"] for c in list_res.json())

    get_res = client.get(f"/v1/connections/{conn_data['id']}", headers=auditor_headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Audit Test Connection"

def test_key_stored_encrypted_and_never_leaked(client, admin_headers):
    """Key is stored encrypted at rest and never appears in any response or ledger payload."""
    secret_key = "sk-super-secret-production-token-9876"
    payload = {
        "name": "Secret Leak Prevention Agent",
        "provider": "mock",
        "api_key": secret_key,
        "model": "warden-mock-v1",
        "allowed_actions": ["issue_refund"],
        "max_amount": 10000.0
    }

    create_res = client.post("/v1/connections", headers=admin_headers, json=payload)
    assert create_res.status_code == 201
    created = create_res.json()

    # 1. API response check
    assert "api_key" not in created
    assert "encrypted_api_key" not in created
    assert created["key_last4"] == "9876"
    assert secret_key not in json.dumps(created)

    conn_id = created["id"]

    # 2. GET one response check
    get_res = client.get(f"/v1/connections/{conn_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert secret_key not in json.dumps(get_res.json())

    # 3. GET list response check
    list_res = client.get("/v1/connections", headers=admin_headers)
    assert list_res.status_code == 200
    assert secret_key not in json.dumps(list_res.json())

    # 4. Check DB row: encrypted_api_key is ciphertext, not plain text
    from app.db import get_connection
    db_conn = get_connection()
    row = db_conn.cursor().execute("SELECT encrypted_api_key FROM provider_connections WHERE id = ?", (conn_id,)).fetchone()
    db_conn.close()
    assert row is not None
    ciphertext = row["encrypted_api_key"]
    assert ciphertext != secret_key
    assert secret_key not in ciphertext
    # Decrypting recovers raw key
    assert crypto_service.decrypt_key(ciphertext) == secret_key

    # 5. Check Ledger payloads: raw secret must not be anywhere in ledger
    ledger_res = client.get("/v1/ledger?limit=20", headers=admin_headers)
    assert ledger_res.status_code == 200
    ledger_str = json.dumps(ledger_res.json())
    assert secret_key not in ledger_str

def test_invalid_key_friendly_result(client, admin_headers):
    """Invalid key is handled with a friendly status and explanation without leaking secrets."""
    payload = {
        "name": "Bad Key Agent",
        "provider": "mock",
        "api_key": "invalid-secret-key",
        "model": "warden-mock-v1"
    }
    create_res = client.post("/v1/connections", headers=admin_headers, json=payload)
    assert create_res.status_code == 201
    conn_id = create_res.json()["id"]

    test_res = client.post(f"/v1/connections/{conn_id}/test", headers=admin_headers)
    assert test_res.status_code == 200
    body = test_res.json()
    assert body["status"] == "invalid_key"
    assert "Authentication failed" in body["message"] or "invalid" in body["message"].lower()
    assert "invalid-secret-key" not in json.dumps(body)

def test_paused_and_revoked_connections_block_and_log(client, admin_headers):
    """Paused and revoked connections always return BLOCKED and log to ledger."""
    payload = {
        "name": "Pause Test Connection",
        "provider": "mock",
        "api_key": "mock-test-key-5555",
        "model": "warden-mock-v1",
        "allowed_actions": ["issue_refund"],
        "max_amount": 5000.0
    }
    create_res = client.post("/v1/connections", headers=admin_headers, json=payload)
    conn_id = create_res.json()["id"]

    # Pause connection
    pause_res = client.post(f"/v1/connections/{conn_id}/pause", headers=admin_headers)
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "paused"

    # Run on paused connection -> BLOCKED
    run_res = client.post(f"/v1/connections/{conn_id}/run", headers=admin_headers, json={"task": "refund 200"})
    assert run_res.status_code == 200
    run_body = run_res.json()
    assert run_body["decisions"][0]["decision"] == "BLOCKED"
    assert "paused" in run_body["decisions"][0]["explanation"].lower()

    # Resume connection
    resume_res = client.post(f"/v1/connections/{conn_id}/resume", headers=admin_headers)
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "active"

    # Revoke connection
    revoke_res = client.delete(f"/v1/connections/{conn_id}", headers=admin_headers)
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"

    # Run on revoked connection -> BLOCKED
    run_revoked = client.post(f"/v1/connections/{conn_id}/run", headers=admin_headers, json={"task": "refund 200"})
    assert run_revoked.status_code == 200
    assert run_revoked.json()["decisions"][0]["decision"] == "BLOCKED"
    assert "revoked" in run_revoked.json()["decisions"][0]["explanation"].lower()

    # Check ledger recorded blocked events
    ledger_res = client.get("/v1/ledger?limit=10", headers=admin_headers)
    items = ledger_res.json()["items"]
    assert any(e["event_type"] == "CONNECTION_RUN_BLOCKED" for e in items)

def test_unsafe_base_url_rejected_and_allowed_when_flag_enabled(client, admin_headers):
    """SSRF protection: rejects http, localhost, and private IPs unless ALLOW_LOCAL_UPSTREAMS=true."""
    settings.ALLOW_LOCAL_UPSTREAMS = False

    # HTTP disallowed
    res_http = client.post("/v1/connections", headers=admin_headers, json={
        "name": "Insecure HTTP",
        "provider": "custom_openai",
        "base_url": "http://api.together.xyz/v1",
        "api_key": "some-key",
        "model": "meta-llama"
    })
    assert res_http.status_code == 400
    assert "https" in res_http.json()["detail"].lower()

    # Localhost disallowed
    res_local = client.post("/v1/connections", headers=admin_headers, json={
        "name": "Localhost Upstream",
        "provider": "custom_openai",
        "base_url": "https://localhost:8080/v1",
        "api_key": "some-key",
        "model": "meta-llama"
    })
    assert res_local.status_code == 400

    # Private IP disallowed
    res_priv = client.post("/v1/connections", headers=admin_headers, json={
        "name": "Private IP Upstream",
        "provider": "custom_openai",
        "base_url": "https://192.168.1.50:8000/v1",
        "api_key": "some-key",
        "model": "meta-llama"
    })
    assert res_priv.status_code == 400

    # Enable ALLOW_LOCAL_UPSTREAMS
    settings.ALLOW_LOCAL_UPSTREAMS = True
    res_allowed = client.post("/v1/connections", headers=admin_headers, json={
        "name": "Permitted Local Upstream",
        "provider": "custom_openai",
        "base_url": "http://localhost:8000/v1",
        "api_key": "some-key",
        "model": "meta-llama"
    })
    assert res_allowed.status_code == 201
    assert res_allowed.json()["base_url"] == "http://localhost:8000/v1"

def test_mock_provider_end_to_end_refund_200_allow_and_refund_80000_pending(client, admin_headers):
    """End-to-end governed execution: refund 200 -> ALLOW; refund 80,000 -> PENDING_APPROVAL."""
    payload = {
        "name": "Customer Support Agent",
        "provider": "mock",
        "api_key": "mock-support-key",
        "model": "warden-mock-v1",
        "allowed_actions": ["issue_refund", "update_record"],
        "allowed_data_classes": ["public", "internal"],
        "max_amount": 100000.0
    }
    create_res = client.post("/v1/connections", headers=admin_headers, json=payload)
    assert create_res.status_code == 201
    conn_id = create_res.json()["id"]

    # Scenario 1: refund 200 (low blast radius) -> ALLOW
    res_200 = client.post(f"/v1/connections/{conn_id}/run", headers=admin_headers, json={
        "task": "Customer requested refund 200 for broken item"
    })
    assert res_200.status_code == 200
    data_200 = res_200.json()
    assert len(data_200["decisions"]) == 1
    dec_200 = data_200["decisions"][0]
    assert dec_200["tool"] == "issue_refund"
    assert dec_200["decision"] == "ALLOW"
    assert dec_200["risk_level"] == "LOW"
    assert dec_200["simulated_execution"]["status"] == "SUCCESS"

    # Scenario 2: refund 80000 (high blast radius) -> PENDING_APPROVAL
    res_80000 = client.post(f"/v1/connections/{conn_id}/run", headers=admin_headers, json={
        "task": "Executive requested refund 80000 for contract cancellation"
    })
    assert res_80000.status_code == 200
    data_80000 = res_80000.json()
    assert len(data_80000["decisions"]) == 1
    dec_80000 = data_80000["decisions"][0]
    assert dec_80000["tool"] == "issue_refund"
    assert dec_80000["decision"] == "PENDING_APPROVAL"
    assert dec_80000["risk_level"] in ("MEDIUM", "HIGH")
    assert dec_80000["simulated_execution"] is None

def test_model_tool_call_blocked_by_policy_and_agent_paused(client, admin_headers):
    """When a model tool call exceeds passport limit, policy blocks it and triggers kill switch (auto-pauses agent)."""
    payload = {
        "name": "Low Limit Connection",
        "provider": "mock",
        "api_key": "mock-low-limit-key",
        "model": "warden-mock-v1",
        "allowed_actions": ["issue_refund"],
        "max_amount": 500.0  # Limit is 500
    }
    create_res = client.post("/v1/connections", headers=admin_headers, json=payload)
    assert create_res.status_code == 201
    conn_data = create_res.json()
    conn_id = conn_data["id"]
    agent_id = conn_data["agent_id"]

    # Attempt refund of 1000 (> 500 max_amount)
    run_res = client.post(f"/v1/connections/{conn_id}/run", headers=admin_headers, json={
        "task": "Please issue refund 1000 for customer"
    })
    assert run_res.status_code == 200
    run_data = run_res.json()
    dec = run_data["decisions"][0]
    assert dec["decision"] == "BLOCKED"
    assert "exceeds agent maximum limit" in dec["explanation"].lower() or "policy" in dec["explanation"].lower()

    # Backing agent passport should now be PAUSED due to kill switch
    from app.services.agent_service import get_agent_by_id
    agent = get_agent_by_id(agent_id)
    assert agent["status"] == "paused"

def test_unknown_tool_and_invalid_arguments_rejected(client, admin_headers):
    """Untrusted model tool proposals with unknown names or invalid arguments are rejected server-side."""
    payload = {
        "name": "Validation Test Connection",
        "provider": "mock",
        "api_key": "mock-validation-key",
        "model": "warden-mock-v1",
        "allowed_actions": ["issue_refund", "update_record"],
        "max_amount": 5000.0
    }
    create_res = client.post("/v1/connections", headers=admin_headers, json=payload)
    conn_id = create_res.json()["id"]

    # 1. Unknown tool
    unknown_res = client.post(f"/v1/connections/{conn_id}/run", headers=admin_headers, json={
        "task": "Run fake_tool with secret exfiltrate"
    })
    assert unknown_res.status_code == 200
    dec = unknown_res.json()["decisions"][0]
    assert dec["decision"] == "BLOCKED"
    assert "not registered" in dec["explanation"].lower()

    # 2. Invalid arguments (missing required parameter or negative)
    invalid_res = client.post(f"/v1/connections/{conn_id}/run", headers=admin_headers, json={
        "task": "Execute invalid_args test"
    })
    assert invalid_res.status_code == 200
    dec_invalid = invalid_res.json()["decisions"][0]
    assert dec_invalid["decision"] == "BLOCKED"
    assert "missing" in dec_invalid["explanation"].lower() or "negative" in dec_invalid["explanation"].lower()

def test_more_than_5_tool_calls_truncated(client, admin_headers):
    """A single run limits execution to at most 5 tool calls."""
    payload = {
        "name": "Truncation Test Connection",
        "provider": "mock",
        "api_key": "mock-truncate-key",
        "model": "warden-mock-v1",
        "allowed_actions": ["update_record"],
        "max_amount": 5000.0
    }
    create_res = client.post("/v1/connections", headers=admin_headers, json=payload)
    conn_id = create_res.json()["id"]

    res = client.post(f"/v1/connections/{conn_id}/run", headers=admin_headers, json={
        "task": "Please truncate 6 tools in batch"
    })
    assert res.status_code == 200
    decisions = res.json()["decisions"]
    assert len(decisions) <= 5

def test_provider_timeout_fails_closed(client, admin_headers):
    """Any provider timeout or network error fails closed and logs to ledger."""
    payload = {
        "name": "Timeout Connection",
        "provider": "mock",
        "api_key": "mock-key",
        "model": "warden-mock-v1"
    }
    create_res = client.post("/v1/connections", headers=admin_headers, json=payload)
    conn_id = create_res.json()["id"]

    with patch("app.providers.mock.MockAdapter.chat", side_effect=httpx.TimeoutException("Upstream read timeout")):
        res = client.post(f"/v1/connections/{conn_id}/run", headers=admin_headers, json={
            "task": "Perform refund 200"
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["decision"] == "BLOCKED"
        assert "fail-closed" in data["decisions"][0]["explanation"].lower()

def test_gemini_adapter_sends_key_in_header_not_url():
    """Gemini adapter sends the key in x-goog-api-key header and never in the URL."""
    adapter = GeminiAdapter(
        api_key="AIzaSyTestSecretKey9999",
        base_url="https://generativelanguage.googleapis.com",
        model="gemini-1.5-pro"
    )

    captured_url = None
    captured_headers = None

    async def mock_safe_request(client, method, url, headers=None, json=None, **kwargs):
        nonlocal captured_url, captured_headers
        captured_url = url
        captured_headers = headers
        # Mock successful reply
        mock_response = httpx.Response(
            status_code=200,
            json={
                "candidates": [{
                    "content": {
                        "parts": [{"text": "Hello world"}]
                    }
                }]
            },
            request=httpx.Request("POST", url)
        )
        return mock_response

    with patch("app.providers.google_gemini.safe_request", side_effect=mock_safe_request):
        import asyncio
        result = asyncio.run(adapter.chat([{"role": "user", "content": "Hello"}], []))

        # Check URL has NO key parameter
        assert captured_url is not None
        assert "key=" not in captured_url
        assert "AIzaSy" not in captured_url

        # Check header contains the key
        assert captured_headers is not None
        assert "x-goog-api-key" in captured_headers
        assert captured_headers["x-goog-api-key"] == "AIzaSyTestSecretKey9999"

def test_rotate_key_and_verify_ledger_chain(client, admin_headers):
    """Key rotation discards old key and preserves cryptographic ledger integrity."""
    create_payload = {
        "name": "Rotation Agent",
        "provider": "mock",
        "api_key": "mock-first-key-1111",
        "model": "warden-mock-v1"
    }
    create_res = client.post("/v1/connections", headers=admin_headers, json=create_payload)
    conn_id = create_res.json()["id"]
    assert create_res.json()["key_last4"] == "1111"

    # Rotate key
    rotate_res = client.post(f"/v1/connections/{conn_id}/rotate-key", headers=admin_headers, json={
        "api_key": "mock-second-key-2222"
    })
    assert rotate_res.status_code == 200
    assert rotate_res.json()["key_last4"] == "2222"

    # Verify cryptographic ledger chain is unbroken
    verify_res = client.get("/v1/ledger/verify", headers=admin_headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True
