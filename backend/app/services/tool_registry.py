"""WARDEN Demo Tools Registry.
Defines supported demo tools, JSON schemas, security metadata, and untrusted input validators.
Simulated execution: only writes to a demo table or ledger; nothing real is touched.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple
from app.db import get_connection

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "issue_refund": {
        "name": "issue_refund",
        "description": "Issue a financial refund for a specific order or transaction.",
        "data_class": "internal",
        "reversibility": "partially",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Refund amount (must be positive, capped at 1,000,000)."
                },
                "order_id": {
                    "type": "string",
                    "description": "Order or invoice identifier (e.g., ORD-1002)."
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the refund."
                }
            },
            "required": ["amount", "order_id"]
        },
        "derive_amount": lambda args: max(0.0, min(float(args.get("amount", 0.0) or 0.0), 1000000.0)),
        "derive_records_affected": lambda args: 1
    },
    "export_customers": {
        "name": "export_customers",
        "description": "Export customer contact details or records.",
        "data_class": "confidential",
        "reversibility": "irreversible",
        "parameters": {
            "type": "object",
            "properties": {
                "record_limit": {
                    "type": "integer",
                    "description": "Number of customer records to export (min 1, max 50,000)."
                },
                "format": {
                    "type": "string",
                    "description": "Export file format (csv or json)."
                },
                "segment": {
                    "type": "string",
                    "description": "Customer tier or segment."
                }
            },
            "required": []
        },
        "derive_amount": lambda args: 0.0,
        "derive_records_affected": lambda args: max(1, min(int(args.get("record_limit", 100) or 100), 50000))
    },
    "update_record": {
        "name": "update_record",
        "description": "Update a field on an existing customer record or support ticket.",
        "data_class": "internal",
        "reversibility": "reversible",
        "parameters": {
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "string",
                    "description": "ID of the record to update."
                },
                "field": {
                    "type": "string",
                    "description": "Field name to modify."
                },
                "new_value": {
                    "type": "string",
                    "description": "New value to set."
                }
            },
            "required": ["record_id", "field", "new_value"]
        },
        "derive_amount": lambda args: 0.0,
        "derive_records_affected": lambda args: 1
    },
    "delete_database": {
        "name": "delete_database",
        "description": "Permanently drop or delete a database table or cluster.",
        "data_class": "restricted",
        "reversibility": "irreversible",
        "parameters": {
            "type": "object",
            "properties": {
                "database_name": {
                    "type": "string",
                    "description": "Target database identifier."
                },
                "force": {
                    "type": "boolean",
                    "description": "Force deletion flag."
                }
            },
            "required": ["database_name"]
        },
        "derive_amount": lambda args: 0.0,
        "derive_records_affected": lambda args: 10000
    }
}

def get_registered_tool(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve tool metadata by tool name."""
    return TOOL_REGISTRY.get(name)

def get_tools_for_agent(allowed_actions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Return tool registry definitions, filtered by allowed_actions if provided."""
    if allowed_actions is None:
        return list(TOOL_REGISTRY.values())
    return [t for name, t in TOOL_REGISTRY.items() if name in allowed_actions]

def validate_tool_call(
    tool_name: str,
    raw_args: Any
) -> Tuple[bool, Optional[str], Dict[str, Any], float, int, str, str]:
    """
    Validate untrusted tool name and arguments against tool registry.
    Returns:
    (is_valid, error_explanation, sanitized_args, derived_amount, records_affected, data_class, reversibility)
    """
    tool_meta = get_registered_tool(tool_name)
    if not tool_meta:
        return (
            False,
            f"Unknown tool '{tool_name}' is not registered in WARDEN registry",
            {},
            0.0,
            0,
            "restricted",
            "irreversible"
        )

    if not isinstance(raw_args, dict):
        return (
            False,
            f"Malformed tool arguments for '{tool_name}': expected JSON object, got {type(raw_args).__name__}",
            {},
            0.0,
            0,
            tool_meta["data_class"],
            tool_meta["reversibility"]
        )

    # Check required fields
    required_fields = tool_meta["parameters"].get("required", [])
    missing = [f for f in required_fields if f not in raw_args or raw_args[f] is None]
    if missing:
        return (
            False,
            f"Tool '{tool_name}' missing required argument(s): {', '.join(missing)}",
            raw_args,
            0.0,
            0,
            tool_meta["data_class"],
            tool_meta["reversibility"]
        )

    sanitized = dict(raw_args)

    # Specific argument bounds and sanitization
    if tool_name == "issue_refund":
        try:
            amt = float(sanitized.get("amount", 0.0))
            if amt < 0:
                return (
                    False,
                    f"Refund amount cannot be negative: {amt}",
                    sanitized,
                    0.0,
                    0,
                    tool_meta["data_class"],
                    tool_meta["reversibility"]
                )
            sanitized["amount"] = max(0.0, min(amt, 1000000.0))
        except (ValueError, TypeError):
            return (
                False,
                f"Invalid amount value: '{sanitized.get('amount')}' is not a valid number",
                sanitized,
                0.0,
                0,
                tool_meta["data_class"],
                tool_meta["reversibility"]
            )

    elif tool_name == "export_customers":
        try:
            rec_limit = int(sanitized.get("record_limit", 100) or 100)
            sanitized["record_limit"] = max(1, min(rec_limit, 50000))
        except (ValueError, TypeError):
            sanitized["record_limit"] = 100

    derived_amount = tool_meta["derive_amount"](sanitized)
    derived_records = tool_meta["derive_records_affected"](sanitized)
    data_class = tool_meta["data_class"]
    reversibility = tool_meta["reversibility"]

    return (
        True,
        None,
        sanitized,
        derived_amount,
        derived_records,
        data_class,
        reversibility
    )

def execute_simulated_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    agent_id: str,
    decision_id: str
) -> Dict[str, Any]:
    """
    Execute simulated tool by writing to demo simulated executions table.
    Nothing real is touched.
    """
    import json
    from datetime import datetime

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS simulated_tool_executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        arguments TEXT NOT NULL,
        executed_at TEXT NOT NULL,
        result TEXT NOT NULL
    )
    """)

    now = datetime.utcnow().isoformat() + "Z"
    result_text = f"Simulated {tool_name} executed successfully for decision {decision_id}."
    cursor.execute("""
    INSERT INTO simulated_tool_executions (decision_id, agent_id, tool_name, arguments, executed_at, result)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (decision_id, agent_id, tool_name, json.dumps(arguments), now, result_text))
    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "simulated": True,
        "tool": tool_name,
        "summary": result_text,
        "arguments": arguments
    }
