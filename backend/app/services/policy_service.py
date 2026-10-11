"""Open Policy Agent (OPA) client and Python fallback policy evaluator.
Evaluates agent permissions, allowed scope, budget limits, data classes, and restricted actions.
"""
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings

RESTRICTED_ACTIONS = [
    "delete_database",
    "drop_table",
    "bulk_export_pii",
    "modify_iam_roles",
    "bypass_governance",
    "execute_arbitrary_code"
]

def evaluate_python_rules(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure Python rule evaluator implementing the exact semantics of policies/warden.rego.
    Guarantees deterministic pre-execution policy enforcement even without OPA running.
    """
    violations: List[str] = []
    agent = input_data.get("agent", {})
    action = input_data.get("action", "")
    data_class = input_data.get("data_class", "public")
    amount = float(input_data.get("amount", 0.0) or 0.0)

    # 1. Agent status must be active
    status = agent.get("status", "unknown")
    if status != "active":
        violations.append(f"Agent status is '{status}', must be 'active'")

    # 2. Globally restricted actions are permanently denied to AI agents
    if action in RESTRICTED_ACTIONS:
        violations.append(f"Action '{action}' is globally restricted for AI agents (requires human execution only)")

    # 3. Action must be within agent passport scope
    allowed_actions = agent.get("allowed_actions", [])
    if action not in allowed_actions:
        violations.append(f"Action '{action}' is not in agent allowed scope: {allowed_actions}")

    # 4. Data classification must be permitted for this agent
    allowed_data_classes = agent.get("allowed_data_classes", [])
    if data_class not in allowed_data_classes:
        violations.append(f"Data classification '{data_class}' exceeds agent allowed data classes: {allowed_data_classes}")

    # 5. Amount cannot exceed agent budget cap
    max_amount = float(agent.get("max_amount", 0.0) or 0.0)
    if amount > max_amount:
        violations.append(f"Requested amount {amount} exceeds agent maximum limit of {max_amount}")

    allow = len(violations) == 0
    return {
        "allow": allow,
        "violations": violations,
        "engine": "python_fallback"
    }

async def evaluate_policy(
    agent: Dict[str, Any],
    action: str,
    data_class: str,
    amount: float,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluate policy using OPA HTTP endpoint if available, falling back to Python evaluator.
    """
    input_data = {
        "agent": {
            "agent_id": agent.get("agent_id"),
            "name": agent.get("name"),
            "owner": agent.get("owner"),
            "status": agent.get("status"),
            "allowed_actions": agent.get("allowed_actions", []),
            "allowed_data_classes": agent.get("allowed_data_classes", []),
            "max_amount": float(agent.get("max_amount", 0.0) or 0.0),
        },
        "action": action,
        "data_class": data_class,
        "amount": float(amount or 0.0),
        "params": params or {}
    }

    # Try OPA HTTP if configured and reachable
    if settings.OPA_URL:
        try:
            async with httpx.AsyncClient(timeout=settings.OPA_TIMEOUT_SECONDS) as client:
                resp = await client.post(settings.OPA_URL, json={"input": input_data})
                if resp.status_code == 200:
                    result = resp.json().get("result", {})
                    # OPA returns {"allow": bool, "violations": [...]}
                    allow = result.get("allow", False)
                    violations = result.get("violations", [])
                    return {
                        "allow": bool(allow),
                        "violations": violations,
                        "engine": "opa"
                    }
        except Exception:
            # OPA unreachable or timeout -> graceful fallback
            pass

    # If OPA is not reached or fallback enabled:
    return evaluate_python_rules(input_data)
