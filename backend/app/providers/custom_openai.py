"""Custom OpenAI-compatible provider adapter."""
from app.providers.openai import OpenAIAdapter

class CustomOpenAIAdapter(OpenAIAdapter):
    """Adapter for any OpenAI-compatible API endpoint with custom base_url."""

    DEFAULT_BASE_URL = "https://api.together.xyz/v1"
