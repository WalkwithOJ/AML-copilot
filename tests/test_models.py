import pytest
from pydantic import ValidationError
from src.models import Citation, RedFlag, TriageBrief


def _citation(source_id="reg_1", source_type="regulation"):
    return Citation(source_id=source_id, source_type=source_type)


def _red_flag(severity="high"):
    return RedFlag(
        description="Test flag",
        severity=severity,
        citations=[_citation()],
    )


def _brief(**overrides):
    defaults = dict(
        risk_tier="high",
        typology_match="Structuring",
        red_flags=[_red_flag()],
        recommended_action="escalate",
        sar_narrative_draft="",
        reasoning_summary="Test reasoning",
        reasoning_citations=[_citation()],
    )
    return TriageBrief(**{**defaults, **overrides})


class TestCitation:
    def test_valid_regulation(self):
        c = _citation(source_type="regulation")
        assert c.source_type == "regulation"

    def test_invalid_source_type(self):
        with pytest.raises(ValidationError):
            Citation(source_id="x", source_type="made_up")


class TestRedFlag:
    def test_requires_at_least_one_citation(self):
        with pytest.raises(ValidationError):
            RedFlag(description="no cite", severity="high", citations=[])

    def test_all_severities(self):
        for sev in ("low", "medium", "high", "critical"):
            rf = RedFlag(description="d", severity=sev, citations=[_citation()])
            assert rf.severity == sev

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            RedFlag(description="d", severity="extreme", citations=[_citation()])


class TestTriageBrief:
    def test_valid_brief(self):
        b = _brief()
        assert b.risk_tier == "high"
        assert b.recommended_action == "escalate"

    def test_requires_at_least_one_red_flag(self):
        with pytest.raises(ValidationError):
            _brief(red_flags=[])

    def test_requires_at_least_one_reasoning_citation(self):
        with pytest.raises(ValidationError):
            _brief(reasoning_citations=[])

    def test_all_risk_tiers(self):
        for tier in ("low", "medium", "high", "critical"):
            b = _brief(risk_tier=tier)
            assert b.risk_tier == tier

    def test_all_recommended_actions(self):
        for action in ("close", "monitor", "escalate", "file_sar"):
            b = _brief(recommended_action=action)
            assert b.recommended_action == action

    def test_invalid_risk_tier(self):
        with pytest.raises(ValidationError):
            _brief(risk_tier="extreme")

    def test_model_dump_roundtrip(self):
        b = _brief()
        data = b.model_dump()
        b2 = TriageBrief(**data)
        assert b == b2
