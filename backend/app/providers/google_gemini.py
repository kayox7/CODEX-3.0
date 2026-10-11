"""Google Gemini adapter with function calling.
CRITICAL: The API key is passed in the header `x-goog-api-key`, NEVER in the URL query string!
"""
import json
from typing import Any, Dict, List, Optional
import httpx
from app.providers.base import BaseProviderAdapter
from app.services.security_service import safe_request

class GeminiAdapter(BaseProviderAdapter):
    """Adapter for Google Gemini generateContent API with function declarations."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"

    def _format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        declarations = []
        for t in tools:
            declarations.append({
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}})
            })
        return [{"function_declarations": declarations}]

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        # Strictly send key via header, NEVER in URL query parameter
        url = f"{self.base_url}/v1beta/models/{self.model}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "content-type": "application/json"
        }

        contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "model" if role in ("assistant", "model") else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}]
                })

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        payload: Dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["system_instruction"] = system_instruction

        if tools:
            payload["tools"] = self._format_tools(tools)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await safe_request(client, "POST", url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API returned status {resp.status_code}: {resp.text}")

            data = resp.json()
            text_parts = []
            tool_calls = []

            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "text" in part:
                        text_parts.append(part["text"])
                    if "functionCall" in part:
                        fc = part["functionCall"]
                        tool_calls.append({
                            "name": fc.get("name", ""),
                            "arguments": fc.get("args", {})
                        })

            return {
                "text": " ".join(text_parts).strip() if text_parts else None,
                "tool_calls": tool_calls
            }

    async def test_connection(self) -> str:
        url = f"{self.base_url}/v1beta/models/{self.model}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "content-type": "application/json"
        }
        payload = {
            "contents": [{"parts": [{"text": "Reply OK"}]}]
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await safe_request(client, "POST", url, headers=headers, json=payload)
                if resp.status_code == 200:
                    return "valid"
                if resp.status_code in (401, 403):
                    return "invalid_key"
                if resp.status_code == 400:
                    body_lower = resp.text.lower()
                    if "api_key_invalid" in body_lower or "api key not valid" in body_lower or "key" in body_lower:
                        return "invalid_key"
                    return "error"
                if resp.status_code == 429:
                    return "rate_limited"
                return "error"
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
            return "unreachable"
        except Exception:
            return "error"
