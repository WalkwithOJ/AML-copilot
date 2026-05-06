import os
import json
import boto3
from src.models import TriageBrief


class BedrockClient:
    def __init__(self):
        self.client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        self.model_id = os.getenv("BEDROCK_MODEL_ID")

    def triage(self, system_prompt: str, user_prompt: str) -> TriageBrief:
        tool_schema = {
            "name": "submit_triage",
            "description": "Submit the structured triage brief",
            "input_schema": TriageBrief.model_json_schema(),
        }
        resp = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "tools": [tool_schema],
                "tool_choice": {"type": "tool", "name": "submit_triage"},
            }),
        )
        body = json.loads(resp["body"].read())
        for block in body["content"]:
            if block.get("type") == "tool_use" and block["name"] == "submit_triage":
                return TriageBrief(**block["input"])
        raise ValueError(f"No tool_use block in response: {body}")
