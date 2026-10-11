"""Anthropic Messages API adapter with tool use support."""
import json
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProviderAdapter
from app.services.security_service import safe_request

class AnthropicAdapter(BaseProviderAdapter):
    """Adapter for Anthropic Claude Messages API."""

    DEFAULT_BASE_URL = "https://api.anthropic.com"

    def _format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for t in tools:
            formatted.append({
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {"type": "object", "properties": {}})
            })
        return formatted

    def _extract_system_and_messages(self, messages: List[Dict[str, Any]]) -> tuple[Optional[str], List[Dict[str, Any]]]:
        system_text = None
        user_assistant_msgs = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_text = content
            else:
                user_assistant_msgs.append({
                    "role": role if role in ("user", "assistant") else "user",
                    "content": content
                })
        if not user_assistant_msgs:
            user_assistant_msgs = [{"role": "user", "content": "Hello"}]
        return system_text, user_assistant_msgs

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        system_text, user_msgs = self._extract_system_and_messages(messages)
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": user_msgs
        }
        if system_text:
            payload["system"] = system_text

        if tools:
            payload["tools"] = self._format_tools(tools)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await safe_request(client, "POST", url, headers=headers, json=payload)
            if resp.status_code != 200:
                error_body = resp.text
                raise RuntimeError(f"Anthropic API returned status {resp.status_code}: {error_body}")

            data = resp.json()
            content_blocks = data.get("content", [])
            text_parts = []
            tool_calls = []

            for block in content_blocks:
                b_type = block.get("type")
                if b_type == "text":
                    text_parts.append(block.get("text", ""))
                elif b_type == "tool_use":
                    tool_calls.append({
                        "name": block.get("name", ""),
                        "arguments": block.get("input", {})
                    })

            return {
                "text": " ".join(text_parts).strip() if text_parts else None,
                "tool_calls": tool_calls
            }

    async def test_connection(self) -> str:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "Reply OK"}]
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await safe_request(client, "POST", url, headers=headers, json=payload)
                if resp.status_code == 200:
                    return "valid"
                if resp.status_code in (401, 403):
                    return "invalid_key"
                if resp.status_code == 429:
                    return "rate_limited"
                return "error"
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
            return "unreachable"
        except Exception:
            return "error"
