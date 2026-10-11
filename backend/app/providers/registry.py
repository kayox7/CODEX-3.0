"""Provider registry mapping provider identifiers to adapter classes and UI metadata."""
from typing import Any, Dict, List, Optional, Type
from app.providers.base import BaseProviderAdapter
from app.providers.anthropic import AnthropicAdapter
from app.providers.google_gemini import GeminiAdapter
from app.providers.openai import OpenAIAdapter
from app.providers.deepseek import DeepSeekAdapter
from app.providers.custom_openai import CustomOpenAIAdapter
from app.providers.mock import MockAdapter

PROVIDER_ADAPTER_MAP: Dict[str, Type[BaseProviderAdapter]] = {
    "anthropic": AnthropicAdapter,
    "google_gemini": GeminiAdapter,
    "openai": OpenAIAdapter,
    "deepseek": DeepSeekAdapter,
    "custom_openai": CustomOpenAIAdapter,
    "mock": MockAdapter,
}

PROVIDER_METADATA: Dict[str, Dict[str, Any]] = {
    "anthropic": {
        "provider": "anthropic",
        "display_name": "Anthropic Claude",
        "default_base_url": "https://api.anthropic.com",
        "editable_base_url": False,
        "key_format_hint": "sk-ant-api03-...",
        "docs_link_text": "Anthropic Console API Keys",
        "docs_url": "https://console.anthropic.com/settings/keys"
    },
    "google_gemini": {
        "provider": "google_gemini",
        "display_name": "Google Gemini",
        "default_base_url": "https://generativelanguage.googleapis.com",
        "editable_base_url": False,
        "key_format_hint": "AIzaSy...",
        "docs_link_text": "Google AI Studio API Keys",
        "docs_url": "https://aistudio.google.com/app/apikey"
    },
    "openai": {
        "provider": "openai",
        "display_name": "OpenAI GPT",
        "default_base_url": "https://api.openai.com",
        "editable_base_url": False,
        "key_format_hint": "sk-proj-...",
        "docs_link_text": "OpenAI Platform Keys",
        "docs_url": "https://platform.openai.com/api-keys"
    },
    "deepseek": {
        "provider": "deepseek",
        "display_name": "DeepSeek",
        "default_base_url": "https://api.deepseek.com",
        "editable_base_url": False,
        "key_format_hint": "sk-...",
        "docs_link_text": "DeepSeek Platform Keys",
        "docs_url": "https://platform.deepseek.com/api_keys"
    },
    "custom_openai": {
        "provider": "custom_openai",
        "display_name": "Custom OpenAI-Compatible Endpoint",
        "default_base_url": "https://api.together.xyz/v1",
        "editable_base_url": True,
        "key_format_hint": "Bearer API Token",
        "docs_link_text": "Custom OpenAI API Documentation",
        "docs_url": ""
    },
    "mock": {
        "provider": "mock",
        "display_name": "Mock Provider (Offline Demo)",
        "default_base_url": "https://mock.warden.local",
        "editable_base_url": False,
        "key_format_hint": "mock-key-1234",
        "docs_link_text": "WARDEN Local Mock Documentation",
        "docs_url": ""
    }
}

def list_provider_metadata() -> List[Dict[str, Any]]:
    """Return provider metadata array for the UI."""
    return list(PROVIDER_METADATA.values())

def get_provider_adapter(
    provider: str,
    api_key: str,
    base_url: Optional[str] = None,
    model: str = "default-model"
) -> BaseProviderAdapter:
    """Instantiate and return the requested provider adapter."""
    prov_key = (provider or "").strip().lower()
    adapter_cls = PROVIDER_ADAPTER_MAP.get(prov_key)
    if not adapter_cls:
        raise ValueError(
            f"Unsupported provider '{provider}'. Supported providers: {list(PROVIDER_ADAPTER_MAP.keys())}"
        )

    meta = PROVIDER_METADATA.get(prov_key, {})
    default_base = meta.get("default_base_url", "https://api.openai.com")

    # Editable only for custom_openai
    final_base_url = (base_url or default_base).strip() if prov_key == "custom_openai" else default_base

    return adapter_cls(api_key=api_key, base_url=final_base_url, model=model)
