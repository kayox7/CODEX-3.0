"""WARDEN SDK Client and pre-execution interceptor."""
import functools
import inspect
import json
import time
from typing import Any, Callable, Dict, Optional
import httpx

from warden_sdk.exceptions import (
    WardenBlocked,
    WardenApprovalTimeout,
    WardenPolicyViolation,
    WardenError
)

class Warden:
    """
    WARDEN SDK Client.
    Provides `@warden.guard(...)` pre-execution interceptor for AI agent tools.
    """
    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: str = "",
        agent_id: str = "support_agent_01",
        poll_interval: float = 0.5,
        poll_timeout: float = 30.0,
        fail_closed: bool = True,
        http_client: Optional[Any] = None
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.agent_id = agent_id
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.fail_closed = fail_closed
        self.http_client = http_client

    def _request_governance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send pre-execution action request to WARDEN control layer."""
        url = f"{self.api_url}/v1/actions/request"
        headers = {
            "Content-Type": "application/json",
            "X-Warden-Api-Key": self.api_key
        }

        try:
            if self.http_client:
                res = self.http_client.post(url, json=payload, headers=headers)
            else:
                with httpx.Client(timeout=5.0) as client:
                    res = client.post(url, json=payload, headers=headers)

            if res.status_code == 200:
                return res.json()
            elif res.status_code == 401:
                raise WardenBlocked(f"WARDEN Authentication failed: {res.text}")
            else:
                raise WardenBlocked(f"WARDEN returned HTTP {res.status_code}: {res.text}")
        except WardenBlocked:
            raise
        except Exception as e:
            if self.fail_closed:
                raise WardenBlocked(f"Governance unreachable (Fail-Closed triggered): {e}") from e
            raise WardenError(f"Governance connection error: {e}") from e

    def _poll_decision(self, decision_id: str) -> Dict[str, Any]:
        """Poll until human approval or rejection/timeout is returned."""
        url = f"{self.api_url}/v1/actions/decision/{decision_id}"
        start_time = time.time()

        while time.time() - start_time < self.poll_timeout:
            try:
                with httpx.Client(timeout=3.0) as client:
                    res = client.get(url)
                    if res.status_code == 200:
                        data = res.json()
                        decision = data.get("decision")
                        if decision in ("ALLOW", "BLOCKED", "HUMAN_ONLY"):
                            return data
            except Exception as e:
                # Polling hiccup: keep trying until timeout
                pass

            time.sleep(self.poll_interval)

        raise WardenApprovalTimeout(
            f"Human approval SLA timed out after {self.poll_timeout}s for decision '{decision_id}'"
        )

    def guard(
        self,
        action: str,
        data_class: str = "public",
        reversibility: str = "partially",
        amount_param: Optional[str] = "amount",
        records_param: Optional[str] = "records_affected"
    ):
        """
        Decorator intercepting AI agent tool invocation before execution.
        """
        def decorator(fn: Callable):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                # 1. Inspect parameters to extract amount, records, and arguments
                sig = inspect.signature(fn)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                params = dict(bound_args.arguments)

                # Extract amount
                amount = 0.0
                if amount_param and amount_param in params:
                    try:
                        amount = float(params[amount_param])
                    except (ValueError, TypeError):
                        amount = 0.0

                # Extract records
                records = 0
                if records_param and records_param in params:
                    try:
                        records = int(params[records_param])
                    except (ValueError, TypeError):
                        records = 0

                # 2. Build pre-execution governance payload
                payload = {
                    "agent_id": self.agent_id,
                    "action": action,
                    "params": params,
                    "amount": amount,
                    "records_affected": records,
                    "data_class": data_class,
                    "reversibility": reversibility
                }

                # 3. Intercept & send to WARDEN control layer
                decision_res = self._request_governance(payload)
                decision = decision_res.get("decision")
                decision_id = decision_res.get("decision_id")
                explanation = decision_res.get("explanation", "")

                # 4. Handle Decision
                if decision == "ALLOW":
                    # Execute tool function
                    result = fn(*args, **kwargs)
                    return result

                elif decision == "PENDING_APPROVAL":
                    # Action blast radius requires human sign-off: poll for resolution
                    poll_result = self._poll_decision(decision_id)
                    final_decision = poll_result.get("decision")
                    if final_decision == "ALLOW":
                        result = fn(*args, **kwargs)
                        return result
                    else:
                        raise WardenBlocked(
                            f"Action '{action}' was blocked by human reviewer: {poll_result.get('explanation')}",
                            decision_id=decision_id
                        )

                elif decision in ("BLOCKED", "HUMAN_ONLY"):
                    raise WardenBlocked(
                        f"Action '{action}' blocked by WARDEN: {explanation}",
                        decision_id=decision_id
                    )

                else:
                    # Unknown decision -> fail closed
                    raise WardenBlocked(
                        f"Action '{action}' denied: unexpected governance decision '{decision}'",
                        decision_id=decision_id
                    )

            return wrapper
        return decorator
