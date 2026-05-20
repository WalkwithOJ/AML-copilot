import re
import uuid
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

_ANALYZER: AnalyzerEngine | None = None
_ANONYMIZER: AnonymizerEngine | None = None

ENTITIES = ["PERSON", "LOCATION", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN", "CREDIT_CARD"]
ACCT_RE = re.compile(r"\b\d{8,12}\b")


def _get_analyzer() -> AnalyzerEngine:
    global _ANALYZER
    if _ANALYZER is None:
        _ANALYZER = AnalyzerEngine()
    return _ANALYZER


def _get_anonymizer() -> AnonymizerEngine:
    global _ANONYMIZER
    if _ANONYMIZER is None:
        _ANONYMIZER = AnonymizerEngine()
    return _ANONYMIZER


def redact(text: str) -> tuple[str, dict]:
    """Returns (tokenized_text, token_map). token_map maps token -> original."""
    token_map: dict[str, str] = {}

    def _replace_acct(m):
        token = f"[ACCT_{uuid.uuid4().hex[:6].upper()}]"
        token_map[token] = m.group(0)
        return token

    text = ACCT_RE.sub(_replace_acct, text)
    results = _get_analyzer().analyze(text=text, entities=ENTITIES, language="en")

    # Sort by start position descending to avoid offset drift during replacement
    results_sorted = sorted(results, key=lambda r: r.start, reverse=True)
    redacted = text
    entity_tokens: dict[str, list[str]] = {}

    for r in results_sorted:
        count = entity_tokens.get(r.entity_type, [])
        idx = len(count) + 1
        token = f"[{r.entity_type}_{idx:03d}]"
        entity_tokens.setdefault(r.entity_type, []).append(token)
        token_map[token] = redacted[r.start:r.end]
        redacted = redacted[:r.start] + token + redacted[r.end:]

    return redacted, token_map


def rehydrate(text: str, token_map: dict) -> str:
    for token, original in token_map.items():
        text = text.replace(token, original)
    return text
