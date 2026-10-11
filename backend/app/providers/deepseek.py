"""DeepSeek OpenAI-compatible adapter."""
from app.providers.openai import OpenAIAdapter

class DeepSeekAdapter(OpenAIAdapter):
    """Adapter for DeepSeek AI with OpenAI-compatible tool calling."""

    DEFAULT_BASE_URL = "https://api.deepseek.com"
