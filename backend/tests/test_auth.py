"""Tests for Authentication and Role-Based Access Control (RBAC)."""
import pytest

@pytest.mark.parametrize("username,expected_role", [
    ("admin", "admin"),
    ("approver", "approver"),
    ("risklead", "risk_lead"),
    ("exec", "executive"),
    ("auditor", "auditor"),
])
def test_login_works_for_each_seeded_role(client, username, expected_role):
    """Every seeded user role can log in with demo123 and receive a valid JWT token."""
    res = client.post("/auth/login", json={"username": username, "password": "demo123"})
    assert res.status_code == 200, f"Failed for {username}: {res.text}"
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == username
    assert data["user"]["role"] == expected_role

def test_wrong_password_returns_401(client):
    """Invalid credentials must return 401 Unauthorized."""
    # Wrong password for existing user
    res = client.post("/auth/login", json={"username": "admin", "password": "incorrect_password"})
    assert res.status_code == 401
    assert "Invalid username or password" in res.json()["detail"]

    # Non-existent user
    res = client.post("/auth/login", json={"username": "unknown_user", "password": "demo123"})
    assert res.status_code == 401
    assert "Invalid username or password" in res.json()["detail"]

def test_auditor_cannot_create_or_pause_agents_but_admin_can(client, admin_headers, auditor_headers):
    """
    Auditor role is read-only for governance:
    - Auditor receives 403 on agent creation
    - Auditor receives 403 on agent pausing
    - Admin succeeds on both
    """
    new_agent_payload = {
        "agent_id": "test_bot_01",
        "name": "Test Governance Bot",
        "owner": "admin",
        "purpose": "Unit testing permissions",
        "allowed_actions": ["view_order"],
        "allowed_data_classes": ["public"],
        "max_amount": 500.0,
        "status": "active"
    }

    # 1. Auditor attempts to create agent -> 403
    auditor_create_res = client.post("/agents", headers=auditor_headers, json=new_agent_payload)
    assert auditor_create_res.status_code == 403
    assert "Access denied" in auditor_create_res.json()["detail"]

    # 2. Auditor attempts to pause agent -> 403
    auditor_pause_res = client.post("/agents/support_agent_01/pause", headers=auditor_headers, json={"reason": "Audit hold"})
    assert auditor_pause_res.status_code == 403
    assert "Access denied" in auditor_pause_res.json()["detail"]

    # 3. Admin creates agent -> 201
    admin_create_res = client.post("/agents", headers=admin_headers, json=new_agent_payload)
    assert admin_create_res.status_code == 201
    assert admin_create_res.json()["agent_id"] == "test_bot_01"

    # 4. Admin pauses agent -> 200
    admin_pause_res = client.post("/agents/support_agent_01/pause", headers=admin_headers, json={"reason": "Security maintenance"})
    assert admin_pause_res.status_code == 200
    assert admin_pause_res.json()["status"] == "paused"
