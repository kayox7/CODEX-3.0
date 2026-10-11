"""Tamper-evident cryptographically chained append-only ledger service.
Each entry hash = SHA256(prev_hash + canonical_json(payload) + timestamp).
Includes chain verification and dev-only tampering simulation.
"""
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from app.db import get_connection

GENESIS_HASH = "0" * 64

def canonical_json(data: Any) -> str:
    """Produce deterministic canonical JSON string."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

def compute_entry_hash(prev_hash: str, payload: Dict[str, Any], timestamp_str: str) -> str:
    """Compute SHA-256 hash of prev_hash + canonical_json(payload) + timestamp."""
    canonical_payload = canonical_json(payload)
    raw = f"{prev_hash}{canonical_payload}{timestamp_str}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def append_ledger_entry(
    event_type: str,
    actor: str,
    payload: Dict[str, Any],
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """Append a new tamper-evident record to the ledger."""
    conn = get_connection()
    cursor = conn.cursor()

    if not timestamp:
        timestamp = datetime.utcnow().isoformat() + "Z"

    # Fetch previous entry to get prev_hash
    cursor.execute("SELECT id, hash FROM ledger_entries ORDER BY id DESC LIMIT 1")
    last_row = cursor.fetchone()
    prev_hash = last_row["hash"] if last_row else GENESIS_HASH

    entry_hash = compute_entry_hash(prev_hash, payload, timestamp)
    payload_json = json.dumps(payload)

    cursor.execute("""
    INSERT INTO ledger_entries (timestamp, event_type, actor, payload, prev_hash, hash)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (timestamp, event_type, actor, payload_json, prev_hash, entry_hash))

    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": entry_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "actor": actor,
        "payload": payload,
        "prev_hash": prev_hash,
        "hash": entry_hash
    }

def get_ledger_entries(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieve ledger entries ordered by id descending."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, timestamp, event_type, actor, payload, prev_hash, hash FROM ledger_entries ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    rows = cursor.fetchall()
    conn.close()

    entries = []
    for row in rows:
        entries.append({
            "id": row["id"],
            "timestamp": row["timestamp"],
            "event_type": row["event_type"],
            "actor": row["actor"],
            "payload": json.loads(row["payload"]),
            "prev_hash": row["prev_hash"],
            "hash": row["hash"]
        })
    return entries

def verify_ledger_chain() -> Dict[str, Any]:
    """
    Walk the entire ledger from oldest to newest.
    Verify:
    1. prev_hash matches the hash of preceding record (or GENESIS for id=1).
    2. hash matches SHA256(prev_hash + canonical_json(payload) + timestamp).
    Returns verification result with details and index of first broken record.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, event_type, actor, payload, prev_hash, hash FROM ledger_entries ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {
            "valid": True,
            "total_entries": 0,
            "broken_index": None,
            "broken_entry_id": None,
            "message": "Ledger is empty (0 entries). Chain integrity intact."
        }

    expected_prev_hash = GENESIS_HASH

    for idx, row in enumerate(rows):
        entry_id = row["id"]
        ts = row["timestamp"]
        actual_prev_hash = row["prev_hash"]
        actual_hash = row["hash"]
        payload = json.loads(row["payload"])

        # Check link integrity
        if actual_prev_hash != expected_prev_hash:
            return {
                "valid": False,
                "total_entries": len(rows),
                "broken_index": idx,
                "broken_entry_id": entry_id,
                "reason": "LINK_BROKEN",
                "message": f"Link broken at entry ID {entry_id} (index {idx}): prev_hash '{actual_prev_hash[:16]}...' does not match prior hash '{expected_prev_hash[:16]}...'"
            }

        # Check cryptographic hash integrity
        recomputed_hash = compute_entry_hash(actual_prev_hash, payload, ts)
        if recomputed_hash != actual_hash:
            return {
                "valid": False,
                "total_entries": len(rows),
                "broken_index": idx,
                "broken_entry_id": entry_id,
                "reason": "PAYLOAD_TAMPERED",
                "message": f"Tampering detected at entry ID {entry_id} (index {idx}): Stored hash '{actual_hash[:16]}...' does not match recomputed SHA-256 '{recomputed_hash[:16]}...'"
            }

        expected_prev_hash = actual_hash

    return {
        "valid": True,
        "total_entries": len(rows),
        "broken_index": None,
        "broken_entry_id": None,
        "message": f"All {len(rows)} ledger entries verified successfully. Cryptographic chain is unbroken and valid."
    }

def tamper_entry(entry_id: int, new_payload: Optional[Dict[str, Any]] = None, tamper_note: str = "TAMPERED_FOR_DEMO") -> Dict[str, Any]:
    """DEV-ONLY: Intentionally alter an existing entry's payload to simulate unauthorized modification."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, event_type, actor, payload, prev_hash, hash FROM ledger_entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Ledger entry {entry_id} not found")

    payload = json.loads(row["payload"])
    if new_payload:
        payload = new_payload
    else:
        payload["_tampered_by_dev"] = True
        payload["_tamper_note"] = tamper_note
        if "amount" in payload:
            payload["amount"] = payload["amount"] + 999999

    cursor.execute("UPDATE ledger_entries SET payload = ? WHERE id = ?", (json.dumps(payload), entry_id))
    conn.commit()
    conn.close()

    return {
        "tampered": True,
        "entry_id": entry_id,
        "message": f"Entry {entry_id} modified in-place without updating cryptographic hash. Verification will now fail."
    }
