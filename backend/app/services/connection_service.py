"""Connection management service for external AI models.
Handles connection registration, credential encryption at rest, backing Agent Passport creation,
governed tool execution, health tests, and tamper-evident ledger logging.
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from app.db import get_connection
from app.providers.registry import get_provider_adapter, PROVIDER_METADATA
from app.schemas.connection import (
    ConnectionCreateRequest,
    ConnectionUpdateRequest,
    ConnectionResponse,
    ToolDecisionDetail,
    ConnectionRunResponse
)
from app.services import (
    agent_service,
    crypto_service,
    decision_service,
    ledger_service,
    security_service,
    tool_registry
)

def _row_to_dict(row) -> Dict[str, Any]:
    """Convert sqlite3.Row to standardized Connection dict."""
    return {
        "id": row["id"],
        "name": row["name"],
        "provider": row["provider"],
        "base_url": row["base_url"],
        "model": row["model"],
        "encrypted_api_key": row["encrypted_api_key"],
        "key_last4": row["key_last4"],
        "agent_id": row["agent_id"],
        "system_prompt": row["system_prompt"],
        "allowed_actions": json.loads(row["allowed_actions"]),
        "allowed_data_classes": json.loads(row["allowed_data_classes"]),
        "max_amount": float(row["max_amount"]),
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "last_used_at": row["last_used_at"],
        "last_test_status": row["last_test_status"],
        "request_count": int(row["request_count"]),
        "blocked_count": int(row["blocked_count"])
    }

def _to_public_response(conn_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Strip all internal encryption tokens; expose only safe key_last4."""
    out = dict(conn_dict)
    out.pop("encrypted_api_key", None)
    return out

def get_connection_by_id(connection_id: int | str) -> Optional[Dict[str, Any]]:
    """Retrieve provider connection by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, name, provider, base_url, model, encrypted_api_key, key_last4,
           agent_id, system_prompt, allowed_actions, allowed_data_classes, max_amount,
           status, created_by, created_at, last_used_at, last_test_status,
           request_count, blocked_count
    FROM provider_connections WHERE id = ?
    """, (int(connection_id) if str(connection_id).isdigit() else connection_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_dict(row)

def list_connections() -> List[Dict[str, Any]]:
    """List all provider connections."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, name, provider, base_url, model, encrypted_api_key, key_last4,
           agent_id, system_prompt, allowed_actions, allowed_data_classes, max_amount,
           status, created_by, created_at, last_used_at, last_test_status,
           request_count, blocked_count
    FROM provider_connections ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [_to_public_response(_row_to_dict(r)) for r in rows]

async def create_connection(req: ConnectionCreateRequest, created_by: str) -> Dict[str, Any]:
    """Register a new external AI model connection with backing Agent Passport."""
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    received_at = datetime.utcnow().isoformat() + "Z"

    prov_key = (req.provider or "").strip().lower()
    if prov_key not in PROVIDER_METADATA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider '{req.provider}'. Allowed: {list(PROVIDER_METADATA.keys())}"
        )

    meta = PROVIDER_METADATA[prov_key]
    default_base_url = meta["default_base_url"]

    # Base URL validation
    if prov_key == "custom_openai":
        raw_url = req.base_url or default_base_url
        try:
            base_url = security_service.validate_base_url(raw_url)
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base_url: {ve}"
            )
    else:
        # Standard providers always use default base URL
        base_url = default_base_url

    # Key validation and encryption
    raw_key = (req.api_key or "").strip()
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider API key is required"
        )

    try:
        encrypted_key = crypto_service.encrypt_key(raw_key)
    except crypto_service.EncryptionConfigError as ece:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(ece)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Key encryption failed: {exc}"
        )

    key_last4 = crypto_service.extract_key_last4(raw_key)

    # 1. Auto-create backing Agent Passport
    agent_id = f"conn_agent_{uuid.uuid4().hex[:8]}"
    passport_data = agent_service.create_agent(
        agent_id=agent_id,
        name=f"{req.name} Agent",
        owner=created_by,
        purpose=f"Connected Agent for {req.name} ({prov_key}:{req.model})",
        allowed_actions=req.allowed_actions,
        allowed_data_classes=req.allowed_data_classes,
        max_amount=float(req.max_amount),
        status="active"
    )

    # 2. Run initial lightweight test call
    test_status = "untested"
    try:
        adapter = get_provider_adapter(prov_key, raw_key, base_url, req.model)
        test_status = await adapter.test_connection()
    except Exception:
        test_status = "error"

    now_iso = datetime.utcnow().isoformat() + "Z"

    # 3. Store in database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO provider_connections (
        name, provider, base_url, model, encrypted_api_key, key_last4, agent_id,
        system_prompt, allowed_actions, allowed_data_classes, max_amount, status,
        created_by, created_at, last_used_at, last_test_status, request_count, blocked_count
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL, ?, 0, 0)
    """, (
        req.name, prov_key, base_url, req.model, encrypted_key, key_last4, agent_id,
        req.system_prompt, json.dumps(req.allowed_actions), json.dumps(req.allowed_data_classes),
        float(req.max_amount), created_by, now_iso, test_status
    ))
    conn_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # 4. Record tamper-evident ledger entry without secrets
    ledger_service.append_ledger_entry(
        event_type="CONNECTION_CREATED",
        actor=created_by,
        payload={
            "request_id": request_id,
            "source_type": "connection",
            "source_name": req.name,
            "provider": prov_key,
            "model": req.model,
            "received_at": received_at,
            "connection_id": conn_id,
            "agent_id": agent_id,
            "key_last4": key_last4,
            "initial_test_status": test_status,
            "status": "active"
        }
    )

    full_conn = get_connection_by_id(conn_id)
    return _to_public_response(full_conn)

def update_connection(
    connection_id: int | str,
    updates: ConnectionUpdateRequest,
    actor: str
) -> Dict[str, Any]:
    """Update connection settings and synchronize backing Agent Passport."""
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    received_at = datetime.utcnow().isoformat() + "Z"

    existing = get_connection_by_id(connection_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    name = updates.name if updates.name is not None else existing["name"]
    model = updates.model if updates.model is not None else existing["model"]
    system_prompt = updates.system_prompt if updates.system_prompt is not None else existing["system_prompt"]
    allowed_actions = updates.allowed_actions if updates.allowed_actions is not None else existing["allowed_actions"]
    allowed_data_classes = updates.allowed_data_classes if updates.allowed_data_classes is not None else existing["allowed_data_classes"]
    max_amount = float(updates.max_amount) if updates.max_amount is not None else existing["max_amount"]

    base_url = existing["base_url"]
    if updates.base_url is not None and existing["provider"] == "custom_openai":
        try:
            base_url = security_service.validate_base_url(updates.base_url)
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base_url: {ve}"
            )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE provider_connections
    SET name = ?, model = ?, base_url = ?, system_prompt = ?,
        allowed_actions = ?, allowed_data_classes = ?, max_amount = ?
    WHERE id = ?
    """, (
        name, model, base_url, system_prompt,
        json.dumps(allowed_actions), json.dumps(allowed_data_classes),
        max_amount, existing["id"]
    ))
    conn.commit()
    conn.close()

    # Synchronize backing agent passport
    agent_service.update_agent(
        existing["agent_id"],
        updates={
            "name": f"{name} Agent",
            "allowed_actions": allowed_actions,
            "allowed_data_classes": allowed_data_classes,
            "max_amount": max_amount
        },
        actor=actor
    )

    # Record in ledger
    ledger_service.append_ledger_entry(
        event_type="CONNECTION_UPDATED",
        actor=actor,
        payload={
            "request_id": request_id,
            "source_type": "connection",
            "source_name": name,
            "provider": existing["provider"],
            "model": model,
            "received_at": received_at,
            "connection_id": existing["id"],
            "key_last4": existing["key_last4"],
            "agent_id": existing["agent_id"]
        }
    )

    updated = get_connection_by_id(existing["id"])
    return _to_public_response(updated)

def pause_connection(connection_id: int | str, actor: str) -> Dict[str, Any]:
    """Pause connection and backing agent passport."""
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    received_at = datetime.utcnow().isoformat() + "Z"

    existing = get_connection_by_id(connection_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE provider_connections SET status = 'paused' WHERE id = ?", (existing["id"],))
    conn.commit()
    conn.close()

    try:
        agent_service.pause_agent(existing["agent_id"], reason="Connection paused by admin", actor=actor)
    except Exception:
        pass

    ledger_service.append_ledger_entry(
        event_type="CONNECTION_PAUSED",
        actor=actor,
        payload={
            "request_id": request_id,
            "source_type": "connection",
            "source_name": existing["name"],
            "provider": existing["provider"],
            "model": existing["model"],
            "received_at": received_at,
            "connection_id": existing["id"],
            "agent_id": existing["agent_id"],
            "key_last4": existing["key_last4"]
        }
    )

    updated = get_connection_by_id(existing["id"])
    return _to_public_response(updated)

def resume_connection(connection_id: int | str, actor: str) -> Dict[str, Any]:
    """Resume a paused connection and backing agent passport."""
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    received_at = datetime.utcnow().isoformat() + "Z"

    existing = get_connection_by_id(connection_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    if existing["status"] == "revoked":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resume a revoked connection"
        )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE provider_connections SET status = 'active' WHERE id = ?", (existing["id"],))
    conn.commit()
    conn.close()

    try:
        agent_service.resume_agent(existing["agent_id"], reason="Connection resumed by admin", actor=actor)
    except Exception:
        pass

    ledger_service.append_ledger_entry(
        event_type="CONNECTION_RESUMED",
        actor=actor,
        payload={
            "request_id": request_id,
            "source_type": "connection",
            "source_name": existing["name"],
            "provider": existing["provider"],
            "model": existing["model"],
            "received_at": received_at,
            "connection_id": existing["id"],
            "agent_id": existing["agent_id"],
            "key_last4": existing["key_last4"]
        }
    )

    updated = get_connection_by_id(existing["id"])
    return _to_public_response(updated)

def revoke_connection(connection_id: int | str, actor: str) -> Dict[str, Any]:
    """Revoke (delete/disable) a connection permanently."""
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    received_at = datetime.utcnow().isoformat() + "Z"

    existing = get_connection_by_id(connection_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE provider_connections SET status = 'revoked' WHERE id = ?", (existing["id"],))
    conn.commit()
    conn.close()

    try:
        agent_service.pause_agent(existing["agent_id"], reason="Connection revoked by admin", actor=actor)
    except Exception:
        pass

    ledger_service.append_ledger_entry(
        event_type="CONNECTION_REVOKED",
        actor=actor,
        payload={
            "request_id": request_id,
            "source_type": "connection",
            "source_name": existing["name"],
            "provider": existing["provider"],
            "model": existing["model"],
            "received_at": received_at,
            "connection_id": existing["id"],
            "agent_id": existing["agent_id"],
            "key_last4": existing["key_last4"]
        }
    )

    updated = get_connection_by_id(existing["id"])
    return _to_public_response(updated)

async def rotate_key(
    connection_id: int | str,
    new_raw_key: str,
    actor: str
) -> Dict[str, Any]:
    """Replace provider API key with a new encrypted key (old key discarded)."""
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    received_at = datetime.utcnow().isoformat() + "Z"

    existing = get_connection_by_id(connection_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    clean_key = (new_raw_key or "").strip()
    if not clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New API key cannot be empty"
        )

    try:
        encrypted_new_key = crypto_service.encrypt_key(clean_key)
    except crypto_service.EncryptionConfigError as ece:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(ece)
        )

    new_key_last4 = crypto_service.extract_key_last4(clean_key)

    # Test the new key
    test_status = "untested"
    try:
        adapter = get_provider_adapter(existing["provider"], clean_key, existing["base_url"], existing["model"])
        test_status = await adapter.test_connection()
    except Exception:
        test_status = "error"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE provider_connections
    SET encrypted_api_key = ?, key_last4 = ?, last_test_status = ?
    WHERE id = ?
    """, (encrypted_new_key, new_key_last4, test_status, existing["id"]))
    conn.commit()
    conn.close()

    ledger_service.append_ledger_entry(
        event_type="CONNECTION_KEY_ROTATED",
        actor=actor,
        payload={
            "request_id": request_id,
            "source_type": "connection",
            "source_name": existing["name"],
            "provider": existing["provider"],
            "model": existing["model"],
            "received_at": received_at,
            "connection_id": existing["id"],
            "agent_id": existing["agent_id"],
            "old_key_last4": existing["key_last4"],
            "new_key_last4": new_key_last4,
            "test_status": test_status
        }
    )

    updated = get_connection_by_id(existing["id"])
    return _to_public_response(updated)

async def test_connection_endpoint(
    connection_id: int | str,
    actor: str
) -> Dict[str, Any]:
    """Test connection reachability and credentials."""
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    received_at = datetime.utcnow().isoformat() + "Z"

    existing = get_connection_by_id(connection_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    try:
        raw_key = crypto_service.decrypt_key(existing["encrypted_api_key"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt provider key at rest"
        )

    adapter = get_provider_adapter(existing["provider"], raw_key, existing["base_url"], existing["model"])
    test_result = await adapter.test_connection()

    # Update in DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE provider_connections SET last_test_status = ? WHERE id = ?", (test_result, existing["id"]))
    conn.commit()
    conn.close()

    ledger_service.append_ledger_entry(
        event_type="CONNECTION_TESTED",
        actor=actor,
        payload={
            "request_id": request_id,
            "source_type": "connection",
            "source_name": existing["name"],
            "provider": existing["provider"],
            "model": existing["model"],
            "received_at": received_at,
            "connection_id": existing["id"],
            "agent_id": existing["agent_id"],
            "key_last4": existing["key_last4"],
            "test_status": test_result
        }
    )

    messages = {
        "valid": "Connection verified: API key is valid and model responded successfully.",
        "invalid_key": "Authentication failed: The provided API key is invalid or unauthorized.",
        "rate_limited": "Upstream rate limit reached: Too many requests sent to the provider.",
        "unreachable": "Network error: Upstream provider endpoint is unreachable or timed out.",
        "error": "Error: Upstream provider returned an unexpected error."
    }

    return {
        "status": test_result,
        "message": messages.get(test_result, f"Test completed with status: {test_result}")
    }

async def run_connection_task(
    connection_id: int | str,
    task: str,
    actor: str
) -> Dict[str, Any]:
    """
    Run governed AI agent task:
    1. Send task and allowed tools to external model.
    2. Intercept EVERY tool call through the WARDEN governance pipeline.
    3. Execute simulated tool only if ALLOW (or approval granted).
    4. Log full trace to tamper-evident ledger.
    """
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    received_at = datetime.utcnow().isoformat() + "Z"

    existing = get_connection_by_id(connection_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found"
        )

    # Check connection status: Paused or revoked connections always return BLOCKED and log
    if existing["status"] != "active":
        explanation = f"Connection '{existing['name']}' is {existing['status']}. Pre-execution controls deny all requests."
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"

        # Increment counts in DB
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE provider_connections
        SET request_count = request_count + 1, blocked_count = blocked_count + 1
        WHERE id = ?
        """, (existing["id"],))
        conn.commit()
        conn.close()

        ledger_service.append_ledger_entry(
            event_type="CONNECTION_RUN_BLOCKED",
            actor=actor,
            payload={
                "request_id": request_id,
                "source_type": "connection",
                "source_name": existing["name"],
                "provider": existing["provider"],
                "model": existing["model"],
                "received_at": received_at,
                "connection_id": existing["id"],
                "agent_id": existing["agent_id"],
                "key_last4": existing["key_last4"],
                "task": task,
                "status": existing["status"],
                "explanation": explanation
            }
        )

        return {
            "task": task,
            "model_text": None,
            "decisions": [
                {
                    "tool": "none",
                    "arguments_summary": {},
                    "decision": "BLOCKED",
                    "risk_level": "BLOCKED",
                    "risk_score": 1.0,
                    "explanation": explanation,
                    "decision_id": decision_id,
                    "simulated_execution": None
                }
            ],
            "summary": f"Execution blocked: Connection '{existing['name']}' status is '{existing['status']}'."
        }

    # Decrypt key
    try:
        raw_key = crypto_service.decrypt_key(existing["encrypted_api_key"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt provider API key"
        )

    # Format tools according to agent allowed actions
    allowed_tools = tool_registry.get_tools_for_agent(existing["allowed_actions"])

    # Prepare chat messages
    messages = []
    if existing.get("system_prompt"):
        messages.append({"role": "system", "content": existing["system_prompt"]})
    messages.append({"role": "user", "content": task})

    adapter = get_provider_adapter(existing["provider"], raw_key, existing["base_url"], existing["model"])

    # Execute model call with fail-closed guarantee
    try:
        model_result = await adapter.chat(messages, allowed_tools)
    except Exception as exc:
        # FAIL-CLOSED ON ANY PROVIDER ERROR, TIMEOUT, OR MALFORMED OUTPUT
        fail_id = f"dec_{uuid.uuid4().hex[:12]}"
        err_msg = f"Provider invocation error (fail-closed): {str(exc)}"

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE provider_connections
        SET request_count = request_count + 1, blocked_count = blocked_count + 1
        WHERE id = ?
        """, (existing["id"],))
        conn.commit()
        conn.close()

        ledger_service.append_ledger_entry(
            event_type="CONNECTION_RUN_FAILED",
            actor=actor,
            payload={
                "request_id": request_id,
                "source_type": "connection",
                "source_name": existing["name"],
                "provider": existing["provider"],
                "model": existing["model"],
                "received_at": received_at,
                "connection_id": existing["id"],
                "agent_id": existing["agent_id"],
                "key_last4": existing["key_last4"],
                "task": task,
                "error": err_msg,
                "decision": "BLOCKED"
            }
        )

        return {
            "task": task,
            "model_text": None,
            "decisions": [
                {
                    "tool": "provider_call",
                    "arguments_summary": {},
                    "decision": "BLOCKED",
                    "risk_level": "BLOCKED",
                    "risk_score": 1.0,
                    "explanation": err_msg,
                    "decision_id": fail_id,
                    "simulated_execution": None
                }
            ],
            "summary": "Execution blocked due to provider error or timeout."
        }

    raw_tool_calls = model_result.get("tool_calls", [])
    # Limit one run to at most 5 tool calls
    truncated_tool_calls = raw_tool_calls[:5]

    tool_decisions: List[Dict[str, Any]] = []
    blocked_occurred = False

    for tc in truncated_tool_calls:
        tool_name = tc.get("name", "")
        raw_args = tc.get("arguments", {})

        is_valid, validation_err, sanitized_args, amt, records, data_class, reversibility = (
            tool_registry.validate_tool_call(tool_name, raw_args)
        )

        if not is_valid:
            # Reject unknown tools or malformed arguments
            blocked_occurred = True
            dec_id = f"dec_{uuid.uuid4().hex[:12]}"
            explanation = f"Blocked: {validation_err}"

            ledger_service.append_ledger_entry(
                event_type="ACTION_BLOCKED",
                actor=existing["agent_id"],
                payload={
                    "request_id": request_id,
                    "source_type": "connection",
                    "source_name": existing["name"],
                    "provider": existing["provider"],
                    "model": existing["model"],
                    "received_at": received_at,
                    "decision_id": dec_id,
                    "tool": tool_name,
                    "error": validation_err
                }
            )

            tool_decisions.append({
                "tool": tool_name,
                "arguments_summary": raw_args if isinstance(raw_args, dict) else {},
                "decision": "BLOCKED",
                "risk_level": "BLOCKED",
                "risk_score": 1.0,
                "explanation": explanation,
                "decision_id": dec_id,
                "simulated_execution": None
            })
            continue

        # Valid tool -> Run through existing WARDEN decision flow
        decision_res = await decision_service.process_action_request(
            agent_id=existing["agent_id"],
            action=tool_name,
            params=sanitized_args,
            amount=amt,
            records_affected=records,
            data_class=data_class,
            reversibility=reversibility
        )

        gov_decision = decision_res.get("decision", "BLOCKED")
        if gov_decision in ("BLOCKED", "HUMAN_ONLY"):
            blocked_occurred = True

        simulated_res = None
        if gov_decision == "ALLOW":
            simulated_res = tool_registry.execute_simulated_tool(
                tool_name=tool_name,
                arguments=sanitized_args,
                agent_id=existing["agent_id"],
                decision_id=decision_res["decision_id"]
            )

        tool_decisions.append({
            "tool": tool_name,
            "arguments_summary": sanitized_args,
            "decision": gov_decision,
            "risk_level": decision_res.get("risk_level", "UNKNOWN"),
            "risk_score": decision_res.get("risk_score", 0.0),
            "explanation": decision_res.get("explanation", ""),
            "decision_id": decision_res.get("decision_id", ""),
            "simulated_execution": simulated_res
        })

    # Update connection stats in DB
    now_iso = datetime.utcnow().isoformat() + "Z"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE provider_connections
    SET request_count = request_count + 1,
        blocked_count = blocked_count + ?,
        last_used_at = ?
    WHERE id = ?
    """, (1 if blocked_occurred else 0, now_iso, existing["id"]))
    conn.commit()
    conn.close()

    # Append run ledger entry
    ledger_service.append_ledger_entry(
        event_type="CONNECTION_RUN",
        actor=actor,
        payload={
            "request_id": request_id,
            "source_type": "connection",
            "source_name": existing["name"],
            "provider": existing["provider"],
            "model": existing["model"],
            "received_at": received_at,
            "connection_id": existing["id"],
            "agent_id": existing["agent_id"],
            "key_last4": existing["key_last4"],
            "task": task,
            "proposed_tool_count": len(raw_tool_calls),
            "executed_tool_count": len(tool_decisions),
            "had_block": blocked_occurred
        }
    )

    summary_text = (
        f"Model proposed {len(raw_tool_calls)} tool call(s). "
        f"Evaluated {len(tool_decisions)} governed action(s)."
    )

    return {
        "task": task,
        "model_text": model_result.get("text"),
        "decisions": tool_decisions,
        "summary": summary_text
    }
