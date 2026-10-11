"""Abstract base class for provider adapters."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class BaseProviderAdapter(ABC):
    """Common interface for external AI model adapters."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = 30.0

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Send messages and tool definitions to the upstream AI model.
        Returns dictionary formatted as:
        {
            "text": Optional[str],
            "tool_calls": List[{"name": str, "arguments": Dict[str, Any]}]
        }
        """
        pass

    @abstractmethod
    async def test_connection(self) -> str:
        """
        Lightweight health check call ("Reply OK").
        Returns one of: 'valid' | 'invalid_key' | 'rate_limited' | 'unreachable' | 'error'
        """
        pass
