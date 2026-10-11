"""Agent Passport registry service.
Handles CRUD, status management (active/paused/revoked),
API key generation and hashing, and passport retrieval.
"""
import hashlib
import json
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.db import get_connection
from app.services.ledger_service import append_ledger_entry

def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

def generate_api_key() -> str:
    return f"wrd_{secrets.token_hex(24)}"

def create_agent(
    agent_id: str,
    name: str,
    owner: str,
    purpose: str,
    allowed_actions: List[str],
    allowed_data_classes: List[str],
    max_amount: float,
    status: str = "active",
    custom_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new agent passport with generated or custom API key."""
    conn = get_connection()
    cursor = conn.cursor()

    api_key = custom_api_key or generate_api_key()
    api_key_hash = hash_api_key(api_key)
    api_key_prefix = api_key[:8] + "..."

    now = datetime.utcnow().isoformat() + "Z"

    cursor.execute("""
    INSERT INTO agent_passports (
        agent_id, name, owner, purpose, allowed_actions, allowed_data_classes,
        max_amount, status, api_key_hash, api_key_prefix, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        agent_id, name, owner, purpose,
        json.dumps(allowed_actions),
        json.dumps(allowed_data_classes),
        max_amount, status, api_key_hash, api_key_prefix, now, now
    ))

    conn.commit()
    conn.close()

    passport_data = {
        "agent_id": agent_id,
        "name": name,
        "owner": owner,
        "purpose": purpose,
        "allowed_actions": allowed_actions,
        "allowed_data_classes": allowed_data_classes,
        "max_amount": max_amount,
        "status": status,
        "api_key_prefix": api_key_prefix,
        "created_at": now,
        "updated_at": now
    }

    # Record in ledger
    append_ledger_entry(
        event_type="AGENT_REGISTERED",
        actor=owner,
        payload={"agent_id": agent_id, "name": name, "owner": owner, "status": status, "max_amount": max_amount}
    )

    # Return passport with raw api_key visible once
    passport_data["api_key"] = api_key
    return passport_data

def get_agent_by_id(agent_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an agent passport by agent_id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, agent_id, name, owner, purpose, allowed_actions, allowed_data_classes,
           max_amount, status, api_key_hash, api_key_prefix, created_at, updated_at
    FROM agent_passports WHERE agent_id = ?
    """, (agent_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "agent_id": row["agent_id"],
        "name": row["name"],
        "owner": row["owner"],
        "purpose": row["purpose"],
        "allowed_actions": json.loads(row["allowed_actions"]),
        "allowed_data_classes": json.loads(row["allowed_data_classes"]),
        "max_amount": row["max_amount"],
        "status": row["status"],
        "api_key_hash": row["api_key_hash"],
        "api_key_prefix": row["api_key_prefix"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

def get_all_agents() -> List[Dict[str, Any]]:
    """Retrieve all agent passports."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, agent_id, name, owner, purpose, allowed_actions, allowed_data_classes,
           max_amount, status, api_key_prefix, created_at, updated_at
    FROM agent_passports ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    agents = []
    for row in rows:
        agents.append({
            "id": row["id"],
            "agent_id": row["agent_id"],
            "name": row["name"],
            "owner": row["owner"],
            "purpose": row["purpose"],
            "allowed_actions": json.loads(row["allowed_actions"]),
            "allowed_data_classes": json.loads(row["allowed_data_classes"]),
            "max_amount": row["max_amount"],
            "status": row["status"],
            "api_key_prefix": row["api_key_prefix"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })
    return agents

def update_agent(agent_id: str, updates: Dict[str, Any], actor: str = "admin") -> Optional[Dict[str, Any]]:
    """Update agent passport fields."""
    agent = get_agent_by_id(agent_id)
    if not agent:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    name = updates.get("name", agent["name"])
    purpose = updates.get("purpose", agent["purpose"])
    allowed_actions = json.dumps(updates.get("allowed_actions", agent["allowed_actions"]))
    allowed_data_classes = json.dumps(updates.get("allowed_data_classes", agent["allowed_data_classes"]))
    max_amount = updates.get("max_amount", agent["max_amount"])
    status = updates.get("status", agent["status"])
    now = datetime.utcnow().isoformat() + "Z"

    cursor.execute("""
    UPDATE agent_passports
    SET name = ?, purpose = ?, allowed_actions = ?, allowed_data_classes = ?,
        max_amount = ?, status = ?, updated_at = ?
    WHERE agent_id = ?
    """, (name, purpose, allowed_actions, allowed_data_classes, max_amount, status, now, agent_id))

    conn.commit()
    conn.close()

    append_ledger_entry(
        event_type="AGENT_UPDATED",
        actor=actor,
        payload={"agent_id": agent_id, "updated_fields": list(updates.keys())}
    )

    return get_agent_by_id(agent_id)

def pause_agent(agent_id: str, reason: str = "Manual pause", actor: str = "admin", is_kill_switch: bool = False) -> Dict[str, Any]:
    """Pause an agent passport (Kill Switch or manual)."""
    agent = get_agent_by_id(agent_id)
    if not agent:
        raise ValueError(f"Agent '{agent_id}' not found")

    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat() + "Z"
    cursor.execute("UPDATE agent_passports SET status = 'paused', updated_at = ? WHERE agent_id = ?", (now, agent_id))
    conn.commit()
    conn.close()

    event_type = "KILL_SWITCH_TRIGGERED" if is_kill_switch else "AGENT_PAUSED"
    append_ledger_entry(
        event_type=event_type,
        actor=actor,
        payload={"agent_id": agent_id, "reason": reason, "previous_status": agent["status"]}
    )

    return {
        "agent_id": agent_id,
        "status": "paused",
        "reason": reason,
        "is_kill_switch": is_kill_switch,
        "message": f"Agent '{agent_id}' has been PAUSED. Pre-execution controls will deny all requests."
    }

def resume_agent(agent_id: str, reason: str = "Manual resume", actor: str = "admin") -> Dict[str, Any]:
    """Resume a paused agent passport."""
    agent = get_agent_by_id(agent_id)
    if not agent:
        raise ValueError(f"Agent '{agent_id}' not found")

    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat() + "Z"
    cursor.execute("UPDATE agent_passports SET status = 'active', updated_at = ? WHERE agent_id = ?", (now, agent_id))
    conn.commit()
    conn.close()

    append_ledger_entry(
        event_type="AGENT_RESUMED",
        actor=actor,
        payload={"agent_id": agent_id, "reason": reason, "previous_status": agent["status"]}
    )

    return {
        "agent_id": agent_id,
        "status": "active",
        "reason": reason,
        "message": f"Agent '{agent_id}' has been RESUMED and is now active."
    }

def verify_agent_api_key(agent_id: str, api_key: str) -> bool:
    """Validate raw API key against stored hashed key."""
    agent = get_agent_by_id(agent_id)
    if not agent:
        return False
    expected_hash = agent["api_key_hash"]
    given_hash = hash_api_key(api_key)
    return secrets.compare_digest(expected_hash, given_hash)
