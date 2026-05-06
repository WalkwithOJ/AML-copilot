# AML Copilot — Claude Code Context

## Mission
Build and ship a working v1 of the **AML Copilot** by end of Wednesday. Co-op posting at Nasdaq-Verafin goes live Thursday morning. This project is the portfolio centrepiece for that application.

---

## Project Identity

**Full title:** AML Copilot: Compliance-First Agentic Triage with PII-Safe LLM Access and Auditable Reasoning

**The one-liner:** AML analysts can't send raw customer PII to a hosted LLM — compliance blocks it. This project builds the architecture that makes it safe to do anyway.

**The triage value:** 95%+ of AML alerts are false positives. Each takes 30+ minutes to investigate. This copilot pre-investigates — entity history, similar past cases, relevant regulations — and produces a structured brief the analyst can accept, edit, or reject in ~3 minutes.

---

## Architecture

```
Raw Alert (with PII)
       ↓
[PII Redaction Layer] ──────→ [Audit Log]
 Presidio + regex              hash-chained
       ↓                         (SHA-256)
Tokenized Alert                      ↑
       ↓                             │
Orchestrator: Claude Sonnet 4.6 ─────┤
via AWS Bedrock                      │
       ↓ (retrieves)                 │
   ┌───┼───────────┐                 │
   ↓   ↓           ↓                 │
Entity  Regulation  Similar Case     │
DB      Vector      Vector Store     │
(Postgres+pgvector)  (past alerts)   │
   ↓   ↓           ↓                 │
   └──→ Sequential RAG ──────────────┤
       ↓                             │
Tokenized Triage Brief ──────────────┘
(Pydantic, citation-enforced)
       ↓
[PII Rehydration] — local only
       ↓
Streamlit UI → analyst
       ↓
Feedback (accept/edit/reject) → Postgres
```

---

## Tech Stack (v1)

| Layer | Choice | Why |
|---|---|---|
| LLM | Claude Sonnet 4.6 via AWS Bedrock | On resume; quality matters |
| PII | Microsoft Presidio + regex | Production-grade NER |
| Database | PostgreSQL + pgvector via Supabase | On resume; zero infra setup |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | Free, local, 384-dim, fast |
| Validation | Pydantic v2 with citation enforcement | Structural hallucination guard |
| UI | Streamlit | Single-file, ship fast |
| Deploy | Hugging Face Spaces | Free, instant, public URL |
| Synthetic data | Faker | Realistic alerts without real PII |

**Budget:** $30 USD hard cap on Bedrock spend. Sonnet 4.6 only — no Haiku, quality matters for interviews.

---

## Environment Variables

```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=            # grab from Bedrock console after model access granted
DATABASE_URL=                # Supabase connection string (postgres://...)
```

---

## Project Structure

```
aml-copilot/
├── requirements.txt
├── .env.example
├── schema.sql
├── src/
│   ├── __init__.py
│   ├── models.py           # Pydantic schemas (DONE)
│   ├── clients/
│   │   └── bedrock.py      # Bedrock wrapper (DONE)
│   ├── redaction.py        # PII redaction + rehydration (DONE)
│   ├── audit.py            # Hash-chained audit log (DONE)
│   ├── synthetic.py        # Faker alert generator (TODO)
│   ├── retrieval.py        # pgvector queries (TODO)
│   └── triage.py           # Main orchestrator (TODO)
└── app.py                  # Streamlit UI (TODO)
```

---

## requirements.txt

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
```

After install: `python -m spacy download en_core_web_sm`

---

## schema.sql (paste into Supabase SQL editor)

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

---

## src/models.py (DONE)

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

---

## src/clients/bedrock.py (DONE)

```python
import os, json, boto3
from src.models import TriageBrief

class BedrockClient:
    def __init__(self):
        self.client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION"))
        self.model_id = os.getenv("BEDROCK_MODEL_ID")

    def triage(self, system_prompt: str, user_prompt: str) -> TriageBrief:
        tool_schema = {
            "name": "submit_triage",
            "description": "Submit the structured triage brief",
            "input_schema": TriageBrief.model_json_schema()
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

---

## src/redaction.py (DONE)

```python
import re, uuid
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

ANALYZER = AnalyzerEngine()
ANONYMIZER = AnonymizerEngine()

ENTITIES = ["PERSON", "LOCATION", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN", "CREDIT_CARD"]
ACCT_RE = re.compile(r"\b\d{8,12}\b")

def redact(text: str) -> tuple[str, dict]:
    """Returns (tokenized_text, token_map). token_map maps token -> original."""
    token_map: dict[str, str] = {}

    def _replace_acct(m):
        token = f"[ACCT_{uuid.uuid4().hex[:6].upper()}]"
        token_map[token] = m.group(0)
        return token

    text = ACCT_RE.sub(_replace_acct, text)
    results = ANALYZER.analyze(text=text, entities=ENTITIES, language="en")
    counters: dict[str, int] = {}

    for r in results:
        counters[r.entity_type] = counters.get(r.entity_type, 0) + 1

    anon = ANONYMIZER.anonymize(text=text, analyzer_results=results,
        operators={e: {"type": "replace", "new_value": f"[{e}]"} for e in ENTITIES})
    redacted = anon.text

    for entity_type, count in counters.items():
        for i in range(1, count + 1):
            token = f"[{entity_type}_{i:03d}]"
            redacted = redacted.replace(f"[{entity_type}]", token, 1)
            original = results[i - 1]
            token_map[token] = text[original.start:original.end]

    return redacted, token_map

def rehydrate(text: str, token_map: dict) -> str:
    for token, original in token_map.items():
        text = text.replace(token, original)
    return text
```

---

## src/audit.py (DONE)

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
            (alert_id,)
        )
        row = cur.fetchone()
        prev = row[0] if row else None
        curr = hash_payload(prev, payload)
        cur.execute(
            "INSERT INTO audit_log (alert_id, step, payload, prev_hash, curr_hash) VALUES (%s,%s,%s,%s,%s)",
            (alert_id, step, json.dumps(payload, default=str), prev, curr),
        )
    conn.commit()
    return curr

def verify_chain(conn, alert_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT step, payload, prev_hash, curr_hash FROM audit_log WHERE alert_id=%s ORDER BY id",
            (alert_id,)
        )
        rows = cur.fetchall()
    expected_prev = None
    for step, payload, prev_hash, curr_hash in rows:
        if prev_hash != expected_prev:
            return False
        if hash_payload(prev_hash, json.loads(payload) if isinstance(payload, str) else payload) != curr_hash:
            return False
        expected_prev = curr_hash
    return True
```

---

## What Still Needs Building (TODO)

### src/synthetic.py
- Use Faker to generate ~50 realistic AML alerts across at least 4 typologies:
  - Structuring (smurfing)
  - Trade-based money laundering
  - Shell company layering
  - Rapid movement / round-tripping
- Each alert: narrative text (with real names, account numbers), linked entities + transaction in Postgres
- Store embedding of narrative in `alerts.embedding` using `all-MiniLM-L6-v2`
- Mix of true_positive and false_positive ground truth labels

### src/retrieval.py
- `get_entity_history(conn, entity_id) -> str` — JOIN across entities + transactions, return formatted string + raw SQL for UI display
- `search_regulations(conn, query_embedding, top_k=3) -> list[dict]` — pgvector cosine similarity on `regulations` table
- `find_similar_cases(conn, alert_embedding, top_k=3) -> list[dict]` — pgvector cosine similarity on `alerts` table, exclude self
- All functions return `{"id", "content", "source", "similarity"}` dicts so `source_id` maps cleanly to Pydantic Citations

### src/triage.py
Main orchestrator. For a given alert_id:
1. Fetch raw alert narrative from Postgres
2. `log_step(conn, alert_id, "raw_alert", {...})`
3. `redact(narrative)` → tokenized text + token_map
4. `log_step(conn, alert_id, "redaction", {"token_count": len(token_map)})`
5. Embed tokenized text → retrieve regs + similar cases
6. `log_step(conn, alert_id, "retrieval", {"reg_ids": [...], "case_ids": [...]})`
7. Build system + user prompt with retrieved context
8. Call `BedrockClient().triage(system, user)` → TriageBrief
9. `log_step(conn, alert_id, "llm_response", brief.model_dump())`
10. Rehydrate brief text fields via `rehydrate(text, token_map)`
11. `log_step(conn, alert_id, "rehydration", {"complete": True})`
12. Return `(brief, token_map, audit_steps, sql_executed)`

### app.py (Streamlit)
Three columns / sections:
1. **Left panel:** alert selector dropdown, metadata, "Run Triage" button
2. **Main panel:** triage brief output — risk tier (coloured badge), typology, red flags (each with citation source), recommended action, SAR draft narrative
3. **Expandable panels at bottom:**
   - `🔄 Raw vs Redacted` — side-by-side raw narrative and what Bedrock actually saw
   - `🔒 Audit Trail` — table of hash-chained steps with prev/curr hash
   - `🔍 SQL Executed` — the entity history query that ran
4. Accept / Edit / Reject buttons → update `alerts.status` in Postgres

---

## Regulatory Corpus (ingest before building retrieval)

Download these — all public:
- FATF: https://www.fatf-gafi.org/content/dam/fatf-gafi/guidance/ML-TF-Risks-Vulnerabilities-Professional-Money-Laundering.pdf
- FINTRAC AML guidance: https://www.fintrac-canafe.gc.ca/guidance-directives/overview-apercu/Guide4/4-eng
- FinCEN SAR filing tips: https://www.fincen.gov/sites/default/files/shared/SARActivity_Report_CY2022.pdf

Chunk into ~500-token sections, embed with `all-MiniLM-L6-v2`, insert into `regulations` table.

---

## Prompts (use these in triage.py)

**System prompt:**
```
You are an AML investigation assistant embedded in a compliance team at a financial crime detection firm.

You are analyzing a TOKENIZED alert — all PII has been replaced with tokens like [PERSON_001] and [ACCT_001].
You must produce a structured triage brief. Every red flag and piece of reasoning MUST cite a specific
retrieved source using its source_id. If you cannot cite a source for a claim, do not make the claim.

Regulatory context and similar past cases are provided. Do not hallucinate regulations or precedents.
```

**User prompt template:**
```
ALERT (tokenized):
{tokenized_narrative}

ENTITY HISTORY:
{entity_history}

SIMILAR PAST CASES:
{similar_cases}

RELEVANT REGULATIONS:
{regulations}

Produce a complete triage brief. Every claim must cite a source_id from the materials above.
```

---

## Demo Script (90-second Loom)

1. Open app → select a high-risk structuring alert
2. Click "Run Triage" — show brief populating
3. Expand "Raw vs Redacted" — pause, explain: "Bedrock never saw the real names"
4. Expand "Audit Trail" — show hash chain
5. Click "Escalate" → status updates
6. One line to camera: "This is the compliance layer that makes LLMs viable in regulated finance."

---

## What to Emphasise in Application / Interview

1. **Compliance-first** — PII never leaves your boundary raw. Solves the actual production blocker.
2. **Auditability** — hash-chained log + citation enforcement at schema level. SR 11-7 ready.
3. **Shipping velocity** — v1 shipped in ~2 days with Bedrock + Postgres (resume-aligned, not faked).
4. **Vision** — README roadmap: LangGraph agentic conversion, AWS-native deploy, Merkle audit chain, regional Bedrock routing for data residency.
5. **Human-in-the-loop** — copilot augments the analyst, doesn't replace. Verafin is explicit about this.

---

## Post-Application Roadmap (put in README)

- LangGraph agentic orchestrator (replaces sequential RAG)
- AWS Lambda + API Gateway + RDS + Cognito (replace Supabase + HF Spaces)
- Next.js + shadcn UI (replace Streamlit)
- Real Presidio NER with custom AML entity types
- Cryptographic Merkle audit chain
- Regional Bedrock routing for data residency (US/Canada split)
- Eval harness with ragas (retrieval precision, hallucination rate)
- Differential privacy on similar-case retrieval

---

## Biggest Risk

Bedrock model access not granted. **Mitigation:** abstract LLM calls behind `LLMClient` interface with a fallback `AnthropicDirectClient` using the same interface. If Bedrock is still pending, develop against Anthropic API direct — swap the client once access lands. Final demo must use Bedrock.
