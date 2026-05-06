# AML Copilot — Full Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the complete AML Copilot v1 from an empty directory to a working Streamlit demo — PII-safe LLM triage of financial crime alerts with auditable reasoning.

**Architecture:** Raw AML alerts are PII-redacted via Presidio, the tokenized text is embedded and used for pgvector retrieval against regulations and past cases, then passed to Claude via AWS Bedrock (with a direct Anthropic API fallback) to produce a Pydantic-validated, citation-enforced triage brief. Every pipeline step is SHA-256 hash-chained to an audit log. Analysts review the rehydrated brief in Streamlit and accept, edit, or reject it.

**Tech Stack:** Python 3.11+, Streamlit, psycopg2 + pgvector (Supabase), Pydantic v2, sentence-transformers (all-MiniLM-L6-v2), Microsoft Presidio + spaCy, Faker, boto3 (Bedrock), anthropic SDK (fallback), pytest

---

## File Map

| File | Responsibility |
|---|---|
| `requirements.txt` | All Python dependencies |
| `.env.example` | Environment variable template |
| `schema.sql` | Supabase schema — run in SQL editor |
| `src/__init__.py` | Package marker |
| `src/db.py` | psycopg2 connection factory |
| `src/models.py` | Pydantic schemas: Citation, RedFlag, TriageBrief |
| `src/clients/base.py` | Abstract LLMClient interface |
| `src/clients/bedrock.py` | AWS Bedrock implementation |
| `src/clients/anthropic_direct.py` | Anthropic SDK fallback implementation |
| `src/clients/__init__.py` | `get_llm_client()` factory — checks env and returns right client |
| `src/redaction.py` | Presidio PII redaction + token rehydration |
| `src/audit.py` | SHA-256 hash-chained audit log |
| `src/retrieval.py` | pgvector queries: entity history, regulation search, similar cases |
| `src/synthetic.py` | Faker alert generator — 52 alerts, 4 typologies, ~70% TP |
| `src/triage.py` | 12-step orchestrator pipeline |
| `app.py` | Streamlit UI — 3-panel layout with audit trail and raw/redacted diff |
| `scripts/__init__.py` | Package marker |
| `scripts/seed_regulations.py` | Seed 14 FATF/FINTRAC/FinCEN regulation chunks with embeddings |
| `tests/__init__.py` | Package marker |
| `tests/test_models.py` | Pydantic validation tests |
| `tests/test_redaction.py` | PII redaction and rehydration tests |
| `tests/test_audit.py` | Hash chain integrity tests |
| `tests/test_clients.py` | LLM client interface compliance tests |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `schema.sql`
- Create: `src/__init__.py`
- Create: `src/db.py`
- Create: `tests/__init__.py`
- Create: `scripts/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
streamlit==1.39.0
boto3==1.35.0
psycopg2-binary==2.9.9
pgvector==0.3.6
pydantic==2.9.0
faker==30.0.0
presidio-analyzer==2.2.355
presidio-anonymizer==2.2.355
sentence-transformers==3.0.1
python-dotenv==1.0.1
spacy==3.7.5
anthropic>=0.34.0
pytest>=8.0.0
```

- [ ] **Step 2: Create .env.example**

```
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=
DATABASE_URL=
# Fallback: set this if Bedrock access not yet granted — app auto-selects
ANTHROPIC_API_KEY=
```

- [ ] **Step 3: Create schema.sql**

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE entities (
  id           SERIAL PRIMARY KEY,
  external_id  TEXT UNIQUE NOT NULL,
  name         TEXT NOT NULL,
  entity_type  TEXT NOT NULL CHECK (entity_type IN ('individual','business')),
  country      TEXT,
  risk_score   INT DEFAULT 0,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE transactions (
  id           SERIAL PRIMARY KEY,
  sender_id    INT REFERENCES entities(id),
  receiver_id  INT REFERENCES entities(id),
  amount       NUMERIC(14,2) NOT NULL,
  currency     TEXT NOT NULL DEFAULT 'USD',
  txn_type     TEXT,
  occurred_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE alerts (
  id              SERIAL PRIMARY KEY,
  transaction_id  INT REFERENCES transactions(id),
  typology        TEXT,
  raw_narrative   TEXT NOT NULL,
  status          TEXT DEFAULT 'open',
  ground_truth    TEXT CHECK (ground_truth IN ('true_positive','false_positive', NULL)),
  embedding       vector(384),
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE regulations (
  id          SERIAL PRIMARY KEY,
  source      TEXT NOT NULL,
  section     TEXT,
  content     TEXT NOT NULL,
  embedding   vector(384) NOT NULL
);

CREATE TABLE audit_log (
  id          BIGSERIAL PRIMARY KEY,
  alert_id    INT REFERENCES alerts(id),
  step        TEXT NOT NULL,
  payload     JSONB NOT NULL,
  prev_hash   TEXT,
  curr_hash   TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON alerts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX ON regulations USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX ON audit_log(alert_id, id);
```

- [ ] **Step 4: Create src/__init__.py, tests/__init__.py, scripts/__init__.py**

All three are empty files.

- [ ] **Step 5: Create src/db.py**

```python
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))
```

- [ ] **Step 6: Install dependencies**

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Expected: all packages install without error.

- [ ] **Step 7: Commit**

```bash
git init
git add requirements.txt .env.example schema.sql src/__init__.py src/db.py tests/__init__.py scripts/__init__.py
git commit -m "feat: project scaffold — requirements, schema, db helper"
```

---

## Task 2: Pydantic Models

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests — tests/test_models.py**

```python
import pytest
from pydantic import ValidationError
from src.models import Citation, RedFlag, TriageBrief


def test_citation_valid():
    c = Citation(source_id="reg_1", source_type="regulation")
    assert c.source_id == "reg_1"


def test_red_flag_rejects_empty_citations():
    with pytest.raises(ValidationError):
        RedFlag(description="suspicious activity", severity="high", citations=[])


def test_red_flag_valid():
    flag = RedFlag(
        description="Multiple deposits below CTR threshold",
        severity="high",
        citations=[Citation(source_id="reg_1", source_type="regulation")],
    )
    assert flag.severity == "high"


def test_triage_brief_rejects_empty_red_flags():
    with pytest.raises(ValidationError):
        TriageBrief(
            risk_tier="high",
            typology_match="structuring",
            red_flags=[],
            recommended_action="escalate",
            sar_narrative_draft="test",
            reasoning_summary="test",
            reasoning_citations=[Citation(source_id="r1", source_type="regulation")],
        )


def test_triage_brief_valid():
    brief = TriageBrief(
        risk_tier="critical",
        typology_match="structuring",
        red_flags=[
            RedFlag(
                description="Structured deposits",
                severity="critical",
                citations=[Citation(source_id="reg_1", source_type="regulation")],
            )
        ],
        recommended_action="file_sar",
        sar_narrative_draft="Subject made repeated deposits...",
        reasoning_summary="Pattern consistent with structuring.",
        reasoning_citations=[Citation(source_id="reg_1", source_type="regulation")],
    )
    assert brief.risk_tier == "critical"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 3: Create src/models.py**

```python
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
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_models.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: Pydantic schemas — Citation, RedFlag, TriageBrief with citation enforcement"
```

---

## Task 3: LLM Clients

**Files:**
- Create: `src/clients/base.py`
- Create: `src/clients/bedrock.py`
- Create: `src/clients/anthropic_direct.py`
- Create: `src/clients/__init__.py`
- Create: `tests/test_clients.py`

- [ ] **Step 1: Write failing tests — tests/test_clients.py**

```python
from src.clients.base import LLMClient
from src.clients.bedrock import BedrockClient
from src.clients.anthropic_direct import AnthropicDirectClient


def test_bedrock_implements_llm_client():
    assert issubclass(BedrockClient, LLMClient)


def test_anthropic_direct_implements_llm_client():
    assert issubclass(AnthropicDirectClient, LLMClient)


def test_bedrock_has_triage_method():
    assert callable(getattr(BedrockClient, "triage", None))


def test_anthropic_direct_has_triage_method():
    assert callable(getattr(AnthropicDirectClient, "triage", None))
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_clients.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.clients'`

- [ ] **Step 3: Create src/clients/base.py**

```python
from abc import ABC, abstractmethod
from src.models import TriageBrief


class LLMClient(ABC):
    @abstractmethod
    def triage(self, system_prompt: str, user_prompt: str) -> TriageBrief:
        ...
```

- [ ] **Step 4: Create src/clients/bedrock.py**

```python
import os, json, boto3
from src.models import TriageBrief
from src.clients.base import LLMClient


class BedrockClient(LLMClient):
    def __init__(self):
        self.client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION"))
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
```

- [ ] **Step 5: Create src/clients/anthropic_direct.py**

```python
import os, anthropic
from src.models import TriageBrief
from src.clients.base import LLMClient


class AnthropicDirectClient(LLMClient):
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
```

- [ ] **Step 6: Create src/clients/__init__.py**

```python
import os
from src.clients.base import LLMClient
from src.clients.bedrock import BedrockClient


def get_llm_client() -> LLMClient:
    if os.getenv("ANTHROPIC_API_KEY"):
        from src.clients.anthropic_direct import AnthropicDirectClient
        return AnthropicDirectClient()
    if not os.getenv("BEDROCK_MODEL_ID"):
        raise ValueError("Set either ANTHROPIC_API_KEY or BEDROCK_MODEL_ID in .env")
    return BedrockClient()
```

- [ ] **Step 7: Run — expect PASS**

```bash
pytest tests/test_clients.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/clients/ tests/test_clients.py
git commit -m "feat: LLM client abstraction — Bedrock + Anthropic direct fallback"
```

---

## Task 4: Redaction + Audit

**Files:**
- Create: `src/redaction.py`
- Create: `src/audit.py`
- Create: `tests/test_redaction.py`
- Create: `tests/test_audit.py`

- [ ] **Step 1: Write failing tests — tests/test_redaction.py**

```python
from src.redaction import redact, rehydrate


def test_redacts_person_name():
    text = "John Smith deposited $9,500 at First National Bank."
    redacted, token_map = redact(text)
    assert "John Smith" not in redacted
    assert any("PERSON" in k for k in token_map)


def test_redacts_account_number():
    text = "Funds transferred from account 1234567890 to 9876543210."
    redacted, token_map = redact(text)
    assert "1234567890" not in redacted
    assert "9876543210" not in redacted
    assert sum(1 for k in token_map if "ACCT" in k) == 2


def test_rehydrate_restores_original():
    text = "Jane Doe wired funds from account 1234567890."
    redacted, token_map = redact(text)
    restored = rehydrate(redacted, token_map)
    assert "1234567890" in restored


def test_no_pii_returns_empty_token_map():
    text = "The transaction amount was five hundred dollars in USD."
    redacted, token_map = redact(text)
    assert text == redacted or len(token_map) == 0
```

- [ ] **Step 2: Write failing tests — tests/test_audit.py**

```python
from src.audit import hash_payload, verify_chain


def test_hash_payload_deterministic():
    payload = {"step": "raw_alert", "size": 100}
    assert hash_payload(None, payload) == hash_payload(None, payload)


def test_hash_payload_genesis_differs_from_chained():
    payload = {"step": "test"}
    assert hash_payload(None, payload) != hash_payload("some_prev", payload)


def test_hash_payload_different_payloads_differ():
    assert hash_payload(None, {"a": 1}) != hash_payload(None, {"a": 2})
```

- [ ] **Step 3: Run — expect FAIL**

```bash
pytest tests/test_redaction.py tests/test_audit.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 4: Create src/redaction.py**

```python
import re, uuid
from collections import defaultdict
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

ANALYZER = AnalyzerEngine()
ANONYMIZER = AnonymizerEngine()

ENTITIES = ["PERSON", "LOCATION", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN", "CREDIT_CARD"]
ACCT_RE = re.compile(r"\b\d{8,12}\b")


def redact(text: str) -> tuple[str, dict]:
    """Returns (tokenized_text, token_map). token_map maps token -> original value."""
    token_map: dict[str, str] = {}

    def _replace_acct(m):
        tok = f"[ACCT_{uuid.uuid4().hex[:6].upper()}]"
        token_map[tok] = m.group(0)
        return tok

    text = ACCT_RE.sub(_replace_acct, text)
    results = ANALYZER.analyze(text=text, entities=ENTITIES, language="en")

    # Sort by position so numbering matches Presidio's left-to-right replacement order
    results_sorted = sorted(results, key=lambda r: r.start)

    # Group by entity type preserving text-position order
    type_results: dict[str, list] = defaultdict(list)
    for r in results_sorted:
        type_results[r.entity_type].append(r)

    anon = ANONYMIZER.anonymize(
        text=text,
        analyzer_results=results,
        operators={e: {"type": "replace", "new_value": f"[{e}]"} for e in ENTITIES},
    )
    redacted = anon.text

    # Number each placeholder left-to-right and build token_map
    for entity_type, type_res in type_results.items():
        for i, r in enumerate(type_res, 1):
            new_token = f"[{entity_type}_{i:03d}]"
            redacted = redacted.replace(f"[{entity_type}]", new_token, 1)
            token_map[new_token] = text[r.start:r.end]

    return redacted, token_map


def rehydrate(text: str, token_map: dict) -> str:
    for token, original in token_map.items():
        text = text.replace(token, original)
    return text
```

- [ ] **Step 5: Create src/audit.py**

```python
import hashlib, json


def hash_payload(prev_hash: str | None, payload: dict) -> str:
    h = hashlib.sha256()
    h.update((prev_hash or "GENESIS").encode())
    h.update(json.dumps(payload, sort_keys=True, default=str).encode())
    return h.hexdigest()


def log_step(conn, alert_id: int, step: str, payload: dict) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT curr_hash FROM audit_log WHERE alert_id=%s ORDER BY id DESC LIMIT 1",
            (alert_id,),
        )
        row = cur.fetchone()
        prev = row[0] if row else None
        curr = hash_payload(prev, payload)
        cur.execute(
            "INSERT INTO audit_log (alert_id, step, payload, prev_hash, curr_hash) "
            "VALUES (%s,%s,%s,%s,%s)",
            (alert_id, step, json.dumps(payload, default=str), prev, curr),
        )
    conn.commit()
    return curr


def verify_chain(conn, alert_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT step, payload, prev_hash, curr_hash FROM audit_log "
            "WHERE alert_id=%s ORDER BY id",
            (alert_id,),
        )
        rows = cur.fetchall()
    expected_prev = None
    for _step, payload, prev_hash, curr_hash in rows:
        if prev_hash != expected_prev:
            return False
        computed = hash_payload(
            prev_hash,
            json.loads(payload) if isinstance(payload, str) else payload,
        )
        if computed != curr_hash:
            return False
        expected_prev = curr_hash
    return True
```

- [ ] **Step 6: Run — expect PASS**

```bash
pytest tests/test_redaction.py tests/test_audit.py -v
```

Expected: all tests PASS. (Presidio loads spaCy on first run — allow ~30 seconds.)

- [ ] **Step 7: Commit**

```bash
git add src/redaction.py src/audit.py tests/test_redaction.py tests/test_audit.py
git commit -m "feat: PII redaction (Presidio + regex) and SHA-256 hash-chained audit log"
```

---

## Task 5: Retrieval Module

**Files:**
- Create: `src/retrieval.py`

No unit tests — all three functions require a live DB. Validated as part of the end-to-end smoke test.

- [ ] **Step 1: Create src/retrieval.py**

```python
from collections import defaultdict


def get_entity_history(conn, entity_id: int) -> tuple[str, str]:
    """Returns (formatted_history, sql_used)."""
    sql = """
        SELECT e.name, e.entity_type, e.risk_score,
               t.amount, t.currency, t.txn_type, t.occurred_at,
               s.name AS sender_name, r.name AS receiver_name
        FROM entities e
        JOIN transactions t ON (t.sender_id = e.id OR t.receiver_id = e.id)
        JOIN entities s ON s.id = t.sender_id
        JOIN entities r ON r.id = t.receiver_id
        WHERE e.id = %s
        ORDER BY t.occurred_at DESC
        LIMIT 20
    """
    with conn.cursor() as cur:
        cur.execute(sql, (entity_id,))
        rows = cur.fetchall()

    if not rows:
        return f"No transaction history found for entity {entity_id}.", sql

    name, entity_type, risk_score = rows[0][0], rows[0][1], rows[0][2]
    lines = [f"Entity: {name} ({entity_type}) | Risk Score: {risk_score}"]
    for row in rows:
        _, _, _, amount, currency, txn_type, occurred_at, sender, receiver = row
        lines.append(
            f"  {occurred_at.date()} | {txn_type or 'transfer'} | "
            f"{currency} {amount:,.2f} | {sender} → {receiver}"
        )
    return "\n".join(lines), sql


def _vec_str(embedding: list) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"


def search_regulations(conn, query_embedding: list, top_k: int = 3) -> list[dict]:
    sql = """
        SELECT id, source, section, content,
               1 - (embedding <=> %s::vector) AS similarity
        FROM regulations
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    vec = _vec_str(query_embedding)
    with conn.cursor() as cur:
        cur.execute(sql, (vec, vec, top_k))
        rows = cur.fetchall()
    return [
        {
            "id": str(row[0]),
            "source": row[1],
            "content": f"[{row[1]} § {row[2]}] {row[3]}",
            "similarity": float(row[4]),
        }
        for row in rows
    ]


def find_similar_cases(conn, alert_embedding: list, alert_id: int, top_k: int = 3) -> list[dict]:
    sql = """
        SELECT id, typology, raw_narrative, ground_truth,
               1 - (embedding <=> %s::vector) AS similarity
        FROM alerts
        WHERE id != %s AND embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    vec = _vec_str(alert_embedding)
    with conn.cursor() as cur:
        cur.execute(sql, (vec, alert_id, vec, top_k))
        rows = cur.fetchall()
    return [
        {
            "id": str(row[0]),
            "source": f"case_{row[0]}",
            "content": (
                f"[Past Case #{row[0]} | Typology: {row[1]} | Outcome: {row[3]}] "
                f"{row[2][:300]}..."
            ),
            "similarity": float(row[4]),
        }
        for row in rows
    ]
```

- [ ] **Step 2: Commit**

```bash
git add src/retrieval.py
git commit -m "feat: pgvector retrieval — entity history, regulation search, similar cases"
```

---

## Task 6: Synthetic Data Generator

**Files:**
- Create: `src/synthetic.py`

- [ ] **Step 1: Create src/synthetic.py**

```python
"""Generate ~52 synthetic AML alerts across 4 typologies and seed the database."""
import os, random
from datetime import datetime, timedelta
import psycopg2
from faker import Faker
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

fake = Faker()
embedder = SentenceTransformer("all-MiniLM-L6-v2")


# ── Narrative templates ────────────────────────────────────────────────────

def _structuring(name, acct, bank, city, n, amounts, total, days, tp):
    if tp:
        return (
            f"{name} conducted {n} cash deposits totaling ${total:,.2f} at {bank} branches "
            f"across {city} over {days} days. Account {acct} received all deposits ranging "
            f"from ${min(amounts):,.2f} to ${max(amounts):,.2f}, each below the $10,000 "
            f"Currency Transaction Report threshold. Branch personnel noted customer requested "
            f"amounts remain under the reporting threshold. Pattern consistent with deliberate "
            f"structuring to evade CTR requirements under 31 U.S.C. § 5324."
        )
    return (
        f"{name} made {n} ATM withdrawals totaling ${total:,.2f} over {days} days from "
        f"account {acct} at {bank} in {city}. Amounts ranged from ${min(amounts):,.2f} to "
        f"${max(amounts):,.2f}. Customer is a small business owner with documented cash "
        f"payroll obligations. No indication of intent to evade reporting requirements."
    )


def _trade_based(company, acct, amount, foreign_co, country, goods, markup, name, tp):
    if tp:
        return (
            f"{company} (account {acct}) received wire transfer of ${amount:,.2f} USD from "
            f"{foreign_co} in {country} for purported invoice covering {goods}. Independent "
            f"market pricing analysis indicates goods are overvalued by approximately {markup}%. "
            f"Beneficial owner {name} has prior SAR filings in the past 24 months. Shipping "
            f"documentation contains inconsistencies with declared customs values. Pattern "
            f"consistent with FATF trade-based money laundering typologies."
        )
    return (
        f"{company} (account {acct}) received ${amount:,.2f} USD from {foreign_co} in "
        f"{country} for legitimate export of {goods}. Invoice and shipping documentation are "
        f"consistent and match declared customs values. {name} is registered beneficial owner "
        f"with no adverse history. Transaction commensurate with known business volume."
    )


def _shell_company(s1, a1, s2, a2, amount, address, name, age_days, tp):
    if tp:
        return (
            f"Wire transfer of ${amount:,.2f} from {s1} (account {a1}) to {s2} (account {a2}) "
            f"with no apparent business purpose or documented commercial relationship. Both "
            f"entities incorporated within {age_days} days and share the same registered "
            f"address at {address}. Beneficial owner {name} listed for both entities. No "
            f"employees or operating assets identified. Pattern consistent with shell company "
            f"layering to obscure beneficial ownership."
        )
    return (
        f"Intercompany transfer of ${amount:,.2f} from {s1} (account {a1}) to {s2} "
        f"(account {a2}). Both entities are wholly-owned subsidiaries of the same parent "
        f"corporation with shared administrative address at {address}. Transfer documented "
        f"as intercompany loan repayment per executed agreement. {name} is Group CFO. "
        f"Structure consistent with disclosed corporate treasury policy."
    )


def _rapid_movement(name, acct, amount, currency, foreign_entity, country, days, hops, fee, tp):
    if tp:
        return (
            f"${amount:,.2f} {currency} wire sent from {name} (account {acct}) to "
            f"{foreign_entity} in {country}. Equivalent funds returned to a related domestic "
            f"account within {days} days less a {fee:.1f}% intermediary fee, routed through "
            f"{hops} correspondent accounts across multiple jurisdictions. {name} has no "
            f"documented business relationship with {country}. Pattern consistent with "
            f"round-tripping layering activity."
        )
    return (
        f"${amount:,.2f} {currency} international wire from {name} (account {acct}) to "
        f"{foreign_entity} in {country} for documented real estate purchase. Partial refund "
        f"of ${amount * 0.12:,.2f} received {days} days later due to cancelled transaction. "
        f"Notarized purchase agreement and cancellation documentation provided."
    )


# ── DB helpers ─────────────────────────────────────────────────────────────

def _entity(conn, name, kind, country, risk):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO entities (external_id, name, entity_type, country, risk_score) "
            "VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (f"EXT-{fake.uuid4()[:8].upper()}", name, kind, country, risk),
        )
        return cur.fetchone()[0]


def _transaction(conn, sender_id, receiver_id, amount, txn_type, occurred_at):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO transactions "
            "(sender_id, receiver_id, amount, currency, txn_type, occurred_at) "
            "VALUES (%s,%s,%s,'USD',%s,%s) RETURNING id",
            (sender_id, receiver_id, round(amount, 2), txn_type, occurred_at),
        )
        return cur.fetchone()[0]


def _embed_vec(text: str) -> str:
    vec = embedder.encode(text).tolist()
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _alert(conn, txn_id, typology, narrative, ground_truth):
    vec = _embed_vec(narrative)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO alerts "
            "(transaction_id, typology, raw_narrative, status, ground_truth, embedding) "
            "VALUES (%s,%s,%s,'open',%s,%s::vector)",
            (txn_id, typology, narrative, ground_truth, vec),
        )


# ── Alert factories ────────────────────────────────────────────────────────

def _make_structuring(conn, tp):
    name = fake.name()
    n = random.randint(4, 8)
    amounts = [random.uniform(7500, 9900) for _ in range(n)]
    total = sum(amounts)
    days = random.randint(2, 10)
    bank = fake.company()
    city = fake.city()
    acct = str(random.randint(10**9, 10**10 - 1))
    narrative = _structuring(name, acct, bank, city, n, amounts, total, days, tp)
    e1 = _entity(conn, name, "individual", "US", 75 if tp else 20)
    e2 = _entity(conn, bank, "business", "US", 5)
    txn_id = _transaction(conn, e1, e2, total, "cash_deposit",
                          datetime.now() - timedelta(days=random.randint(1, 30)))
    _alert(conn, txn_id, "structuring", narrative, "true_positive" if tp else "false_positive")


def _make_trade_based(conn, tp):
    company = fake.company()
    name = fake.name()
    acct = str(random.randint(10**9, 10**10 - 1))
    amount = random.uniform(50000, 500000)
    foreign_co = fake.company()
    country = random.choice(["Panama", "Cayman Islands", "British Virgin Islands", "Cyprus", "Malta"])
    goods = random.choice(["electronic components", "industrial machinery", "textiles",
                           "chemical compounds", "software licenses"])
    markup = random.randint(40, 200) if tp else random.randint(0, 15)
    narrative = _trade_based(company, acct, amount, foreign_co, country, goods, markup, name, tp)
    e1 = _entity(conn, foreign_co, "business", country, 80 if tp else 10)
    e2 = _entity(conn, company, "business", "US", 70 if tp else 15)
    txn_id = _transaction(conn, e1, e2, amount, "wire_transfer",
                          datetime.now() - timedelta(days=random.randint(1, 60)))
    _alert(conn, txn_id, "trade_based_ml", narrative, "true_positive" if tp else "false_positive")


def _make_shell(conn, tp):
    name = fake.name()
    s1 = fake.company() + " LLC"
    s2 = fake.company() + " Holdings"
    a1 = str(random.randint(10**9, 10**10 - 1))
    a2 = str(random.randint(10**9, 10**10 - 1))
    amount = random.uniform(100000, 2000000)
    address = fake.address().replace("\n", ", ")
    age_days = random.randint(30, 180) if tp else random.randint(365, 730)
    narrative = _shell_company(s1, a1, s2, a2, amount, address, name, age_days, tp)
    e1 = _entity(conn, s1, "business", "US", 85 if tp else 20)
    e2 = _entity(conn, s2, "business", "US", 85 if tp else 20)
    txn_id = _transaction(conn, e1, e2, amount, "wire_transfer",
                          datetime.now() - timedelta(days=random.randint(1, 90)))
    _alert(conn, txn_id, "shell_company_layering", narrative,
           "true_positive" if tp else "false_positive")


def _make_rapid(conn, tp):
    name = fake.name()
    acct = str(random.randint(10**9, 10**10 - 1))
    amount = random.uniform(25000, 500000)
    currency = random.choice(["USD", "EUR", "GBP", "CAD"])
    foreign_entity = fake.company()
    country = random.choice(["Russia", "China", "UAE", "Nigeria", "Colombia"])
    days = random.randint(2, 14)
    hops = random.randint(3, 7) if tp else 1
    fee = random.uniform(1.5, 8.0) if tp else random.uniform(0.1, 1.0)
    narrative = _rapid_movement(name, acct, amount, currency, foreign_entity,
                                country, days, hops, fee, tp)
    e1 = _entity(conn, name, "individual", "US", 80 if tp else 15)
    e2 = _entity(conn, foreign_entity, "business", country, 75 if tp else 10)
    txn_id = _transaction(conn, e1, e2, amount, "wire_transfer",
                          datetime.now() - timedelta(days=random.randint(1, 45)))
    _alert(conn, txn_id, "rapid_movement", narrative,
           "true_positive" if tp else "false_positive")


# ── Entry point ────────────────────────────────────────────────────────────

FACTORIES = [_make_structuring, _make_trade_based, _make_shell, _make_rapid]


def generate(conn, n: int = 52):
    per_type = n // 4
    for factory in FACTORIES:
        tp_count = round(per_type * 0.7)
        for i in range(per_type):
            factory(conn, tp=i < tp_count)
    conn.commit()
    print(f"Inserted {n} synthetic alerts.")


if __name__ == "__main__":
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    generate(conn)
    conn.close()
    print("Done.")
```

- [ ] **Step 2: Verify parses cleanly**

```bash
python -c "import src.synthetic; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/synthetic.py
git commit -m "feat: Faker synthetic data generator — 52 alerts across 4 AML typologies"
```

---

## Task 7: Triage Orchestrator

**Files:**
- Create: `src/triage.py`

Note: `run_triage` returns `tokenized_narrative` as its 5th value so the app can display the exact text sent to the LLM without re-running redaction.

- [ ] **Step 1: Create src/triage.py**

```python
"""12-step triage pipeline: redact → embed → retrieve → LLM → rehydrate → audit."""
from sentence_transformers import SentenceTransformer
from src.clients import get_llm_client
from src.redaction import redact, rehydrate
from src.audit import log_step
from src.retrieval import get_entity_history, search_regulations, find_similar_cases
from src.models import TriageBrief

_embedder = SentenceTransformer("all-MiniLM-L6-v2")

SYSTEM_PROMPT = (
    "You are an AML investigation assistant embedded in a compliance team at a financial "
    "crime detection firm.\n\n"
    "You are analyzing a TOKENIZED alert — all PII has been replaced with tokens like "
    "[PERSON_001] and [ACCT_001]. You must produce a structured triage brief. Every red flag "
    "and piece of reasoning MUST cite a specific retrieved source using its source_id. If you "
    "cannot cite a source for a claim, do not make the claim.\n\n"
    "Regulatory context and similar past cases are provided. Do not hallucinate regulations "
    "or precedents."
)

USER_PROMPT_TEMPLATE = """\
ALERT (tokenized):
{tokenized_narrative}

ENTITY HISTORY:
{entity_history}

SIMILAR PAST CASES:
{similar_cases}

RELEVANT REGULATIONS:
{regulations}

Produce a complete triage brief. Every claim must cite a source_id from the materials above."""


def run_triage(
    conn, alert_id: int
) -> tuple[TriageBrief, dict, list[dict], str, str]:
    """Run the full 12-step triage pipeline.

    Returns:
        (brief, token_map, audit_steps, entity_sql, tokenized_narrative)
    """
    # 1. Fetch raw alert
    with conn.cursor() as cur:
        cur.execute(
            "SELECT raw_narrative, transaction_id FROM alerts WHERE id = %s", (alert_id,)
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"Alert {alert_id} not found")
    raw_narrative, transaction_id = row

    # 2. Log raw alert
    log_step(conn, alert_id, "raw_alert", {"narrative_length": len(raw_narrative)})

    # 3. Redact PII
    tokenized_text, token_map = redact(raw_narrative)

    # 4. Log redaction
    log_step(conn, alert_id, "redaction", {"token_count": len(token_map)})

    # 5. Embed tokenized text
    embedding = _embedder.encode(tokenized_text).tolist()

    # Resolve sender entity for history lookup
    entity_sql = ""
    entity_history = "No entity history available."
    if transaction_id:
        with conn.cursor() as cur:
            cur.execute("SELECT sender_id FROM transactions WHERE id = %s", (transaction_id,))
            txn_row = cur.fetchone()
        if txn_row:
            entity_history, entity_sql = get_entity_history(conn, txn_row[0])

    # 6. Retrieve context
    regs = search_regulations(conn, embedding)
    similar = find_similar_cases(conn, embedding, alert_id)

    # 7. Log retrieval
    log_step(conn, alert_id, "retrieval", {
        "reg_ids": [r["id"] for r in regs],
        "case_ids": [c["id"] for c in similar],
    })

    # 8. Build prompts
    reg_text = (
        "\n\n".join(f"[REG_{r['id']}] {r['content']}" for r in regs)
        or "No regulations found."
    )
    case_text = (
        "\n\n".join(f"[CASE_{c['id']}] {c['content']}" for c in similar)
        or "No similar cases found."
    )
    user_prompt = USER_PROMPT_TEMPLATE.format(
        tokenized_narrative=tokenized_text,
        entity_history=entity_history,
        similar_cases=case_text,
        regulations=reg_text,
    )

    # 9. Call LLM
    client = get_llm_client()
    brief = client.triage(SYSTEM_PROMPT, user_prompt)

    # 10. Log LLM response
    log_step(conn, alert_id, "llm_response", brief.model_dump())

    # 11. Rehydrate PII back into text fields
    brief_dict = brief.model_dump()
    brief_dict["sar_narrative_draft"] = rehydrate(brief_dict["sar_narrative_draft"], token_map)
    brief_dict["reasoning_summary"] = rehydrate(brief_dict["reasoning_summary"], token_map)
    for flag in brief_dict["red_flags"]:
        flag["description"] = rehydrate(flag["description"], token_map)
    brief = TriageBrief(**brief_dict)

    # 12. Log rehydration
    log_step(conn, alert_id, "rehydration", {"complete": True})

    # Collect full audit trail
    with conn.cursor() as cur:
        cur.execute(
            "SELECT step, payload, prev_hash, curr_hash, created_at "
            "FROM audit_log WHERE alert_id = %s ORDER BY id",
            (alert_id,),
        )
        audit_steps = [
            {
                "step": r[0],
                "payload": r[1],
                "prev_hash": r[2],
                "curr_hash": r[3],
                "created_at": str(r[4]),
            }
            for r in cur.fetchall()
        ]

    return brief, token_map, audit_steps, entity_sql, tokenized_text
```

- [ ] **Step 2: Verify imports cleanly**

```bash
python -c "from src.triage import run_triage; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/triage.py
git commit -m "feat: 12-step triage orchestrator — redact, retrieve, LLM, rehydrate, audit"
```

---

## Task 8: Regulatory Seed Script

**Files:**
- Create: `scripts/seed_regulations.py`

- [ ] **Step 1: Create scripts/seed_regulations.py**

```python
"""Seed FATF / FINTRAC / FinCEN regulation chunks into the regulations table."""
import os
import psycopg2
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

embedder = SentenceTransformer("all-MiniLM-L6-v2")

REGULATIONS = [
    {
        "source": "FATF",
        "section": "Recommendation 20 — Reporting of Suspicious Transactions",
        "content": (
            "If a financial institution suspects or has reasonable grounds to suspect that funds are "
            "the proceeds of a criminal activity, or are related to terrorist financing, it should be "
            "required, by law, to report promptly its suspicions to the financial intelligence unit (FIU). "
            "The threshold for reporting is reasonable grounds to suspect — not proof or certainty. "
            "Financial institutions should file STRs regardless of whether the transaction is completed "
            "or not. Tipping off the customer about the filing is prohibited."
        ),
    },
    {
        "source": "FATF",
        "section": "Guidance on Structuring / Smurfing Typology",
        "content": (
            "Structuring, also known as smurfing, involves breaking up large sums of cash into smaller "
            "amounts to avoid currency transaction reporting thresholds. Indicators include: multiple "
            "cash deposits on the same day or consecutive days, all below the reporting threshold; "
            "customer expressing knowledge of reporting thresholds; use of multiple branches or agents "
            "to make deposits; pattern inconsistent with the customer's known business activities. "
            "Structuring is a criminal offence under 31 U.S.C. § 5324 in the United States and "
            "equivalent provisions in other FATF member jurisdictions."
        ),
    },
    {
        "source": "FATF",
        "section": "Guidance on Trade-Based Money Laundering",
        "content": (
            "Trade-based money laundering (TBML) involves the misrepresentation of the price, quantity, "
            "or quality of imports or exports to transfer value across borders. Key typologies include: "
            "over-invoicing of exports; under-invoicing of imports; multiple invoicing of the same goods; "
            "falsely described goods or services. Red flags: significant discrepancies between invoice "
            "value and market price; routing of payments through unrelated third-party countries; "
            "counterparties in high-risk jurisdictions; lack of business rationale for trade relationship."
        ),
    },
    {
        "source": "FATF",
        "section": "Red Flags for Shell Company Misuse",
        "content": (
            "Shell companies — legal entities with no genuine operations, employees, or assets — are "
            "frequently used to obscure the beneficial ownership of funds and layer criminal proceeds. "
            "Key indicators: newly incorporated entities with no operating history; multiple entities "
            "sharing the same registered address, directors, or beneficial owners; wire transfers with "
            "no apparent commercial purpose between related entities; entities in high-secrecy "
            "jurisdictions (BVI, Cayman Islands, Panama); inconsistency between stated business purpose "
            "and actual transaction flows; directors acting as nominees."
        ),
    },
    {
        "source": "FATF",
        "section": "Beneficial Ownership Transparency — Recommendation 24",
        "content": (
            "FATF Recommendation 24 requires countries to ensure that adequate, accurate, and current "
            "information on the beneficial ownership of legal persons is available. A beneficial owner "
            "is the natural person who ultimately owns or controls a legal entity. Financial institutions "
            "must identify and verify beneficial owners holding 25% or more of a legal entity. Where "
            "the beneficial owner cannot be identified, this constitutes a red flag requiring enhanced "
            "due diligence and may trigger STR obligations."
        ),
    },
    {
        "source": "FATF",
        "section": "Round-Tripping and Circular Fund Flows",
        "content": (
            "Round-tripping involves moving funds out of a jurisdiction and back in to give them the "
            "appearance of legitimate foreign investment or trade receipts. Red flags: funds sent to a "
            "foreign jurisdiction and returned within a short period (days to weeks); consistent "
            "percentage fees retained by intermediaries with no documented service; use of multiple "
            "correspondent banks with no apparent business justification; sender and ultimate receiver "
            "sharing common beneficial ownership; transaction amounts inconsistent with stated "
            "commercial purpose."
        ),
    },
    {
        "source": "FINTRAC",
        "section": "Guide 4 — Suspicious Transaction Reports for Financial Entities",
        "content": (
            "Financial entities subject to the Proceeds of Crime (Money Laundering) and Terrorist "
            "Financing Act must file a Suspicious Transaction Report (STR) with FINTRAC when there "
            "are reasonable grounds to suspect a transaction is related to money laundering or "
            "terrorist financing. The threshold is reasonable grounds to suspect — not certainty. "
            "Reports must be filed within 30 days of detection. The person submitting the report "
            "must not disclose the filing to the subject. Financial entities must retain records "
            "of the grounds for suspicion."
        ),
    },
    {
        "source": "FINTRAC",
        "section": "Structuring Indicators",
        "content": (
            "FINTRAC guidance identifies the following as indicators of structuring: a client makes "
            "multiple cash transactions on the same day with combined value exceeding $10,000 CAD; "
            "client appears to be structuring transactions to avoid LCTR obligations; client makes "
            "deposits just below $10,000 on consecutive days or at multiple branches; client asks "
            "about reporting thresholds or expresses knowledge that transactions must be reported "
            "above a certain amount; pattern inconsistent with client's known business or income profile."
        ),
    },
    {
        "source": "FINTRAC",
        "section": "Suspicious Transaction Indicators — Wire Transfers",
        "content": (
            "FINTRAC wire transfer red flags: transfers to or from high-risk jurisdictions with no "
            "apparent business rationale; use of multiple accounts to funnel funds before wire "
            "transfer; wire transfers received from anonymous or unrelated third parties followed "
            "by immediate onward transfer; round-dollar wire transfers with no corresponding "
            "commercial invoice; transfers structured to avoid SWIFT reporting or correspondent "
            "bank screening; use of encrypted messaging platforms to arrange transfers."
        ),
    },
    {
        "source": "FinCEN",
        "section": "31 U.S.C. § 5324 — Structuring to Evade CTR Requirements",
        "content": (
            "Under 31 U.S.C. § 5324, it is a federal crime to structure, assist in structuring, "
            "or attempt to structure any transaction with one or more domestic financial institutions "
            "for the purpose of evading Currency Transaction Report requirements. The statute covers "
            "both cash-in and cash-out transactions. The crime does not require that the underlying "
            "funds be derived from illegal activity. Penalties include fines up to $250,000 and "
            "imprisonment up to five years, increasing to ten years if structuring involves more "
            "than $100,000 in any twelve-month period or is connected to another felony."
        ),
    },
    {
        "source": "FinCEN",
        "section": "SAR Filing — Mandatory Disclosure Thresholds",
        "content": (
            "Financial institutions must file a Suspicious Activity Report (SAR) with FinCEN when a "
            "transaction involves at least $5,000 in funds and the institution knows, suspects, or "
            "has reason to suspect that the transaction involves funds from illegal activity, is "
            "designed to evade BSA requirements, lacks a lawful purpose, or involves the use of "
            "the financial institution to facilitate criminal activity. SARs must be filed within "
            "30 calendar days of detection. Institutions must retain SAR documentation for five "
            "years. Filing a SAR creates a safe harbor from civil liability."
        ),
    },
    {
        "source": "FinCEN",
        "section": "Advisory on Trade Finance Red Flags",
        "content": (
            "FinCEN trade finance red flags: significant discrepancy between the value of the "
            "commodity and the market price; the deal involves a commodity that does not match "
            "the counterparty's business; payment for goods routed through unrelated third parties "
            "or multiple jurisdictions; counterparty located in a jurisdiction with weak AML "
            "controls; transaction involves a free trade zone; abnormally large cash payments; "
            "letters of credit structured to avoid reporting thresholds; use of front companies "
            "with limited operational footprint."
        ),
    },
    {
        "source": "FinCEN",
        "section": "Customer Due Diligence Rule — Beneficial Ownership",
        "content": (
            "FinCEN's Customer Due Diligence Rule requires covered financial institutions to identify "
            "and verify the identity of beneficial owners of legal entity customers at account opening. "
            "Beneficial owners are: (1) each individual who directly or indirectly owns 25% or more "
            "of the equity interests; and (2) a single individual with significant responsibility to "
            "control, manage, or direct the entity. Covered institutions must understand the nature "
            "and purpose of customer relationships and conduct ongoing monitoring to detect and "
            "report suspicious transactions."
        ),
    },
    {
        "source": "FinCEN",
        "section": "Round-Tripping and Offshore Layering Indicators",
        "content": (
            "FinCEN round-tripping red flags: funds wired offshore and returned to the same or "
            "related domestic account within a short time period; funds passing through multiple "
            "intermediary accounts with deductions at each stage; use of shell companies in "
            "offshore jurisdictions with no disclosed beneficial owner; transaction amounts "
            "inconsistent with stated investment or business purpose; correspondent bank accounts "
            "used in jurisdictions with weak AML regimes; layering through real estate, commodity "
            "trading, or professional service firms to add apparent legitimacy to the funds."
        ),
    },
]


def seed(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM regulations")
        if cur.fetchone()[0] > 0:
            print("Regulations table already populated — skipping.")
            return

    print(f"Embedding and inserting {len(REGULATIONS)} regulation chunks...")
    for i, reg in enumerate(REGULATIONS, 1):
        vec = embedder.encode(reg["content"]).tolist()
        vec_str = "[" + ",".join(f"{x:.8f}" for x in vec) + "]"
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO regulations (source, section, content, embedding) "
                "VALUES (%s,%s,%s,%s::vector)",
                (reg["source"], reg["section"], reg["content"], vec_str),
            )
        print(f"  [{i}/{len(REGULATIONS)}] {reg['source']} — {reg['section'][:60]}")
    conn.commit()
    print("Done.")


if __name__ == "__main__":
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    seed(conn)
    conn.close()
```

- [ ] **Step 2: Verify parses cleanly**

```bash
python -c "import scripts.seed_regulations; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_regulations.py
git commit -m "feat: regulatory seed — 14 FATF/FINTRAC/FinCEN chunks with embeddings"
```

---

## Task 9: Streamlit App

**Files:**
- Create: `app.py`

- [ ] **Step 1: Create app.py**

```python
import os
import psycopg2
import streamlit as st
from dotenv import load_dotenv
from src.triage import run_triage
from src.audit import verify_chain

load_dotenv()

st.set_page_config(page_title="AML Copilot", layout="wide", page_icon="🔍")

TIER_BADGE = {
    "low":      "#22c55e",
    "medium":   "#f59e0b",
    "high":     "#ef4444",
    "critical": "#7f1d1d",
}
SEVERITY_ICON = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
ACTION_LABEL = {
    "close": ("🟢", "CLOSE"),
    "monitor": ("🔵", "MONITOR"),
    "escalate": ("🟠", "ESCALATE"),
    "file_sar": ("🔴", "FILE SAR"),
}


@st.cache_resource
def _conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def _load_alerts():
    conn = _conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, typology, status, ground_truth, created_at "
            "FROM alerts ORDER BY id DESC LIMIT 200"
        )
        return cur.fetchall()


def _update_status(alert_id: int, status: str):
    conn = _conn()
    with conn.cursor() as cur:
        cur.execute("UPDATE alerts SET status = %s WHERE id = %s", (status, alert_id))
    conn.commit()


# ── Page ───────────────────────────────────────────────────────────────────

st.title("AML Copilot")
st.caption("Compliance-first agentic triage · PII-safe LLM access · Auditable reasoning")

alerts = _load_alerts()

if not alerts:
    st.warning(
        "No alerts in database. "
        "Run `python src/synthetic.py` then `python scripts/seed_regulations.py`."
    )
    st.stop()

left, main = st.columns([1, 2])

# ── Left panel ─────────────────────────────────────────────────────────────

with left:
    st.subheader("Alert Queue")
    options = {
        f"#{a[0]} — {a[1].replace('_', ' ').title()} [{a[2]}]": a[0]
        for a in alerts
    }
    selected_label = st.selectbox("Select alert", list(options.keys()))
    selected_id = options[selected_label]

    sel = next(a for a in alerts if a[0] == selected_id)
    st.markdown(f"**Status:** `{sel[2]}`")
    st.markdown(f"**Typology:** `{sel[1]}`")
    if sel[3]:
        st.markdown(f"**Ground Truth:** `{sel[3]}`")
    st.markdown(f"**Created:** {sel[4].strftime('%Y-%m-%d %H:%M')}")
    st.divider()

    run = st.button("▶ Run Triage", type="primary", use_container_width=True)

# ── Main panel ─────────────────────────────────────────────────────────────

with main:
    if run:
        with st.spinner("Running triage pipeline…"):
            try:
                conn = _conn()
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT raw_narrative FROM alerts WHERE id = %s", (selected_id,)
                    )
                    raw = cur.fetchone()[0]
                brief, token_map, audit_steps, entity_sql, tokenized = run_triage(
                    conn, selected_id
                )
                st.session_state.update({
                    "brief": brief,
                    "token_map": token_map,
                    "audit_steps": audit_steps,
                    "entity_sql": entity_sql,
                    "raw_narrative": raw,
                    "tokenized_narrative": tokenized,
                    "triage_alert_id": selected_id,
                    "chain_valid": verify_chain(conn, selected_id),
                })
            except Exception as e:
                st.error(f"Triage failed: {e}")

    if "brief" not in st.session_state:
        st.info("Select an alert and click **▶ Run Triage** to begin investigation.")
    else:
        brief = st.session_state.brief

        # Risk tier
        color = TIER_BADGE.get(brief.risk_tier, "#6b7280")
        st.markdown(
            f"### Risk Tier &nbsp;"
            f'<span style="background:{color};color:white;padding:4px 14px;'
            f'border-radius:4px;font-weight:bold;font-size:1rem">'
            f"{brief.risk_tier.upper()}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**Typology Match:** {brief.typology_match}")
        st.divider()

        # Red flags
        st.markdown("#### Red Flags")
        for flag in brief.red_flags:
            icon = SEVERITY_ICON.get(flag.severity, "⚪")
            st.markdown(f"{icon} **[{flag.severity.upper()}]** {flag.description}")
            cites = ", ".join(
                f"`{c.source_id}` ({c.source_type})" for c in flag.citations
            )
            st.caption(f"Sources: {cites}")
        st.divider()

        # Recommended action
        emoji, label = ACTION_LABEL.get(brief.recommended_action, ("⚪", brief.recommended_action.upper()))
        st.markdown(f"**Recommended Action:** {emoji} **{label}**")
        st.divider()

        # SAR narrative
        st.markdown("#### SAR Narrative Draft")
        st.text_area(
            label="sar",
            value=brief.sar_narrative_draft,
            height=150,
            key="sar_edit",
            label_visibility="collapsed",
        )

        with st.expander("Reasoning Summary"):
            st.write(brief.reasoning_summary)
            cites = ", ".join(f"`{c.source_id}`" for c in brief.reasoning_citations)
            st.caption(f"Citations: {cites}")

        st.divider()

        # Action buttons
        c1, c2, c3 = st.columns(3)
        aid = st.session_state.triage_alert_id
        with c1:
            if st.button("✅ Accept (TP)", use_container_width=True):
                _update_status(aid, "closed_tp")
                st.success("Marked as true positive.")
        with c2:
            if st.button("✏️ Edit & Save", use_container_width=True):
                _update_status(aid, "closed_edited")
                st.success("Saved with edits.")
        with c3:
            if st.button("❌ Reject (FP)", use_container_width=True):
                _update_status(aid, "closed_fp")
                st.success("Marked as false positive.")

# ── Bottom panels ──────────────────────────────────────────────────────────

if "brief" in st.session_state:
    st.divider()

    with st.expander("🔄 Raw vs Redacted — what the LLM actually saw"):
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("**Raw narrative (with PII)**")
            st.text(st.session_state.raw_narrative)
        with r2:
            st.markdown("**Tokenized alert sent to LLM**")
            st.text(st.session_state.tokenized_narrative)

    with st.expander("🔒 Audit Trail — hash-chained pipeline steps"):
        if st.session_state.get("chain_valid"):
            st.success("Chain integrity verified ✓")
        else:
            st.warning("Chain not yet verified.")
        import pandas as pd
        steps = st.session_state.audit_steps
        if steps:
            df = pd.DataFrame([
                {
                    "Step": s["step"],
                    "Prev Hash": (s["prev_hash"] or "GENESIS")[:16] + "…",
                    "Curr Hash": s["curr_hash"][:16] + "…",
                    "Timestamp": s["created_at"],
                }
                for s in steps
            ])
            st.dataframe(df, use_container_width=True)

    with st.expander("🔍 SQL Executed — entity history query"):
        st.code(
            st.session_state.entity_sql or "No entity SQL captured.", language="sql"
        )
```

- [ ] **Step 2: Verify parses cleanly**

```bash
python -c "import ast; ast.parse(open('app.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Streamlit UI — 3-panel triage interface with audit trail and raw/redacted diff"
```

---

## Task 10: End-to-End Smoke Test

- [ ] **Step 1: Run schema in Supabase**

Open Supabase SQL Editor for your project → paste `schema.sql` → Run.
Expected: tables and indexes created, no errors.

- [ ] **Step 2: Configure .env**

```bash
cp .env.example .env
```

Fill in:
- `DATABASE_URL` — Supabase project settings → Database → Connection string (URI mode)
- Either `ANTHROPIC_API_KEY` (fastest path) OR `BEDROCK_MODEL_ID` + AWS keys

- [ ] **Step 3: Seed regulations**

```bash
python scripts/seed_regulations.py
```

Expected: `Embedding and inserting 14 regulation chunks...` then `Done.`

- [ ] **Step 4: Generate synthetic alerts**

```bash
python src/synthetic.py
```

Expected: `Inserted 52 synthetic alerts.` then `Done.`

- [ ] **Step 5: Run test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Launch app**

```bash
streamlit run app.py
```

Expected: app opens at `http://localhost:8501`, alert dropdown populated with 52 alerts.

- [ ] **Step 7: Demo path**

1. Select a `structuring` alert → click **▶ Run Triage**
2. Verify brief populates: risk tier badge, red flags with citations, recommended action
3. Expand **Raw vs Redacted** — confirm PII in left column, tokens in right
4. Expand **Audit Trail** — 6 steps, chain verified ✓
5. Expand **SQL Executed** — entity history query displayed
6. Click **✅ Accept (TP)** — status updates to `closed_tp`

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "chore: end-to-end smoke test verified"
```

---

## Self-Review

Spec coverage check:
- ✅ requirements.txt + .env.example (Task 1)
- ✅ schema.sql with all 5 tables + ivfflat indexes (Task 1)
- ✅ models.py — Citation, RedFlag, TriageBrief with citation enforcement (Task 2)
- ✅ BedrockClient + AnthropicDirectClient behind LLMClient ABC (Task 3)
- ✅ get_llm_client() auto-selects based on env (Task 3)
- ✅ Presidio redaction with correct per-type token numbering (Task 4)
- ✅ SHA-256 hash-chained audit log with verify_chain (Task 4)
- ✅ pgvector entity history + regulation search + similar case search (Task 5)
- ✅ 52 synthetic alerts, 4 typologies, ~70% TP, with embeddings (Task 6)
- ✅ 12-step orchestrator returning tokenized_narrative for display (Task 7)
- ✅ 14 regulation chunks from FATF/FINTRAC/FinCEN (Task 8)
- ✅ Streamlit 3-panel UI with all specified expandable sections (Task 9)
- ✅ Accept/Edit/Reject updating alerts.status (Task 9)
- ✅ End-to-end smoke test with demo path (Task 10)
