"""Offline Mock Provider Adapter.
Requires no network access. Scripted for integration tests and offline demonstrations.
Generates tool calls based on keywords: refund, export, delete, update.
"""
import re
from typing import Any, Dict, List, Optional
from app.providers.base import BaseProviderAdapter

class MockAdapter(BaseProviderAdapter):
    """Offline mock model adapter for deterministic testing and local demonstrations."""

    DEFAULT_BASE_URL = "https://mock.warden.local"

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        combined_text = ""
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                combined_text += " " + content

        task_lower = combined_text.lower()
        tool_calls = []

        # Check for multiple/many tools test condition
        if "6 tools" in task_lower or "many tools" in task_lower or "truncate" in task_lower:
            for i in range(1, 8):
                tool_calls.append({
                    "name": "update_record",
                    "arguments": {
                        "record_id": f"REC-{i}",
                        "field": "batch_status",
                        "new_value": f"updated_{i}"
                    }
                })
            return {
                "text": "Proposed 7 bulk updates.",
                "tool_calls": tool_calls
            }

        # Check for unknown tool test condition
        if "unknown_tool" in task_lower or "fake_tool" in task_lower:
            tool_calls.append({
                "name": "unauthorized_backdoor_tool",
                "arguments": {"secret": "exfiltrate"}
            })
            return {
                "text": "Proposing unknown action.",
                "tool_calls": tool_calls
            }

        # Check for invalid argument test condition
        if "invalid_args" in task_lower or "invalid argument" in task_lower:
            tool_calls.append({
                "name": "issue_refund",
                "arguments": {"amount": -50.0}  # missing required order_id and negative
            })
            return {
                "text": "Proposing invalid refund arguments.",
                "tool_calls": tool_calls
            }

        # 1. Refund keyword
        if "refund" in task_lower:
            # Extract amount e.g. "refund 200", "refund 80000", "refund rs 80,000"
            amount = 200.0
            match = re.search(r'(?:refund|amount)\D*?([0-9][0-9,]*(?:\.[0-9]+)?)', task_lower)
            if match:
                raw_amt = match.group(1).replace(",", "")
                try:
                    amount = float(raw_amt)
                except ValueError:
                    amount = 200.0

            tool_calls.append({
                "name": "issue_refund",
                "arguments": {
                    "amount": amount,
                    "order_id": "ORD-1002",
                    "reason": "Customer refund requested via mock agent"
                }
            })

        # 2. Export keyword
        if "export" in task_lower:
            tool_calls.append({
                "name": "export_customers",
                "arguments": {
                    "record_limit": 500,
                    "format": "csv",
                    "segment": "enterprise"
                }
            })

        # 3. Delete keyword
        if "delete" in task_lower or "drop" in task_lower:
            tool_calls.append({
                "name": "delete_database",
                "arguments": {
                    "database_name": "production_customer_db",
                    "force": True
                }
            })

        # 4. Update keyword
        if "update" in task_lower:
            tool_calls.append({
                "name": "update_record",
                "arguments": {
                    "record_id": "REC-9001",
                    "field": "account_status",
                    "new_value": "active_verified"
                }
            })

        text = f"Mock agent analyzed the task. Proposed {len(tool_calls)} action(s)." if tool_calls else "Mock agent analyzed the task. No tool action required."
        return {
            "text": text,
            "tool_calls": tool_calls
        }

    async def test_connection(self) -> str:
        # Scripted return values for tests
        key = (self.api_key or "").strip().lower()
        if "invalid" in key:
            return "invalid_key"
        if "rate" in key:
            return "rate_limited"
        if "unreachable" in key or "timeout" in key:
            return "unreachable"
        if "error" in key:
            return "error"
        return "valid"
