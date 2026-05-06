import os
from src.clients.base import LLMClient


def get_llm_client() -> LLMClient:
    """Return Bedrock client if AWS creds present, else Anthropic direct fallback."""
    if os.getenv("BEDROCK_MODEL_ID") and os.getenv("AWS_ACCESS_KEY_ID"):
        from src.clients.bedrock import BedrockClient
        return BedrockClient()
    from src.clients.anthropic_direct import AnthropicDirectClient
    return AnthropicDirectClient()
