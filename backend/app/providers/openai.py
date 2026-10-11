"""OpenAI Chat Completions adapter with tool use support."""
import json
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProviderAdapter
from app.services.security_service import safe_request

class OpenAIAdapter(BaseProviderAdapter):
    """Adapter for OpenAI Chat Completions API with tools."""

    DEFAULT_BASE_URL = "https://api.openai.com"

    def _get_chat_endpoint(self) -> str:
        """Derive standard chat completions endpoint URL."""
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def _format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for t in tools:
            formatted.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}})
                }
            })
        return formatted

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        url = self._get_chat_endpoint()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json"
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages
        }
        if tools:
            payload["tools"] = self._format_tools(tools)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await safe_request(client, "POST", url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API returned status {resp.status_code}: {resp.text}")

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return {"text": None, "tool_calls": []}

            message_obj = choices[0].get("message", {})
            text = message_obj.get("content")
            raw_tool_calls = message_obj.get("tool_calls", [])

            parsed_tool_calls = []
            for tc in raw_tool_calls:
                func_data = tc.get("function", {})
                name = func_data.get("name", "")
                raw_args = func_data.get("arguments", {})
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {"raw": raw_args}
                else:
                    args = raw_args
                parsed_tool_calls.append({"name": name, "arguments": args})

            return {
                "text": text,
                "tool_calls": parsed_tool_calls
            }

    async def test_connection(self) -> str:
        url = self._get_chat_endpoint()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Reply OK"}],
            "max_tokens": 5
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
