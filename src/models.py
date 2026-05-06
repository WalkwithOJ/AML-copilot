from pydantic import BaseModel, Field, field_validator
from typing import Literal


class Citation(BaseModel):
    source_id: str = Field(..., description="ID of retrieved chunk this claim references")
    source_type: Literal["regulation", "similar_case", "entity_history"]


class RedFlag(BaseModel):
    description: str
    severity: Literal["low", "medium", "high", "critical"]
    citations: list[Citation] = Field(..., min_length=1)

    @field_validator("citations")
    @classmethod
    def must_have_citation(cls, v):
        if not v:
            raise ValueError("Every red flag must cite at least one source")
        return v


class TriageBrief(BaseModel):
    risk_tier: Literal["low", "medium", "high", "critical"]
    typology_match: str
    red_flags: list[RedFlag] = Field(..., min_length=1)
    recommended_action: Literal["close", "monitor", "escalate", "file_sar"]
    sar_narrative_draft: str
    reasoning_summary: str
    reasoning_citations: list[Citation] = Field(..., min_length=1)
