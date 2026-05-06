from abc import ABC, abstractmethod
from src.models import TriageBrief


class LLMClient(ABC):
    @abstractmethod
    def triage(self, system_prompt: str, user_prompt: str) -> TriageBrief:
        """Call the LLM and return a validated TriageBrief."""
        ...
