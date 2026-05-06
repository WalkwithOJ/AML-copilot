import os
import anthropic
from src.models import TriageBrief


class AnthropicDirectClient:
    """Fallback client using Anthropic API directly when Bedrock access is pending."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-6"

    def triage(self, system_prompt: str, user_prompt: str) -> TriageBrief:
        tool_schema = {
            "name": "submit_triage",
            "description": "Submit the structured triage brief",
            "input_schema": TriageBrief.model_json_schema(),
        }
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": "submit_triage"},
        )
        for block in resp.content:
            if block.type == "tool_use" and block.name == "submit_triage":
                return TriageBrief(**block.input)
        raise ValueError(f"No tool_use block in response: {resp}")
