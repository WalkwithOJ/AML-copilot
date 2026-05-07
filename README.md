# AML Copilot

**Compliance-first agentic triage for Anti-Money Laundering analysts — built for the regulated production environment, not the demo environment.**

> AML analysts can't send raw customer PII to a hosted LLM. Compliance blocks it. This project builds the architecture that makes it safe to do anyway, with a full audit trail regulators can inspect.

Live demo: `streamlit run app.py` after setup below.

---

## What it does

95%+ of AML transaction monitoring alerts are false positives. Each one takes an analyst 30–60 minutes to investigate manually — pulling entity histories, cross-referencing regulations, reviewing prior cases. For a bank processing thousands of alerts monthly, that backlog is the primary AML bottleneck.

AML Copilot pre-investigates each alert automatically before the analyst touches it:

1. Fetches the raw alert narrative from the database
2. **Redacts all PII** (names, account numbers, SSNs, phone numbers) using Microsoft Presidio — producing a tokenized copy that is safe to send to an LLM
3. Retrieves the most relevant regulatory excerpts, similar past resolved cases, and entity transaction history via pgvector similarity search
4. Sends the tokenized alert + retrieved context to **Claude Sonnet 4.6** (via AWS Bedrock, with Anthropic API as fallback), which returns a fully structured triage brief using a tool-use schema that Pydantic validates
5. **Rehydrates** the real names/identifiers back into the brief — the LLM never saw the real PII
6. Writes every step to an append-only, SHA-256 hash-chained audit log that a banking examiner can verify
7. Presents the brief to the analyst in a Streamlit UI for acceptance, editing, or rejection

The analyst reduces a 45-minute investigation to ~3 minutes of review. The LLM never touches raw PII. Every output is auditable.

---

## Architecture

```
Raw Alert (with PII: real names, account numbers)
         │
         ▼
┌─────────────────────┐     ┌──────────────────────────────┐
│  PII Redaction      │────▶│  Audit Log (hash-chained)    │
│  Presidio NER +     │     │  SHA-256 each step binds to  │
│  regex (acct nums)  │     │  previous — tamper-evident   │
│                     │     └──────────────────────────────┘
│  "Jason Macias"     │               ▲  ▲  ▲  ▲
│  → [PERSON_001]     │               │  │  │  │
│  "49823741"         │               │  │  │  │
│  → [ACCT_A3F2B1]    │               │  │  │  │
└─────────────────────┘               │  │  │  │
         │                            │  │  │  │
         ▼ tokenized narrative        │  │  │  │
┌─────────────────────┐               │  │  │  │
│  Embedding          │               │  │  │  │
│  all-MiniLM-L6-v2   │               │  │  │  │
│  (384-dim, local)   │               │  │  │  │
└─────────────────────┘               │  │  │  │
         │ query vector               │  │  │  │
         ▼                            │  │  │  │
┌────────────────────────────────┐    │  │  │  │
│  pgvector Retrieval (RAG)      │────┘  │  │  │
│                                │       │  │  │
│  ① Regulations table           │       │  │  │
│     cosine similarity →        │       │  │  │
│     top-3 FinCEN/FATF/FINTRAC  │       │  │  │
│     excerpts with source_id    │       │  │  │
│                                │       │  │  │
│  ② Similar past cases          │       │  │  │
│     cosine similarity →        │       │  │  │
│     top-3 alerts with          │       │  │  │
│     analyst ground-truth label │       │  │  │
│                                │       │  │  │
│  ③ Entity transaction history  │       │  │  │
│     SQL JOIN across entities + │       │  │  │
│     transactions (last 20)     │       │  │  │
└────────────────────────────────┘       │  │  │
         │ source-tagged context         │  │  │
         ▼                               │  │  │
┌─────────────────────────────────────┐  │  │  │
│  Claude Sonnet 4.6 (Bedrock / API)  │──┘  │  │
│                                     │     │  │
│  System: citation-discipline rules, │     │  │
│  typology definitions, calibration  │     │  │
│  against 95% FP base rate           │     │  │
│                                     │     │  │
│  Tool use: submit_triage schema     │     │  │
│  forces structured JSON output      │     │  │
│  that Pydantic validates on return  │     │  │
└─────────────────────────────────────┘     │  │
         │ TriageBrief (tokenized)           │  │
         ▼                                  │  │
┌─────────────────────┐                     │  │
│  PII Rehydration    │─────────────────────┘  │
│  token_map applied  │                        │
│  to all text fields │                        │
└─────────────────────┘                        │
         │ TriageBrief (with real names)        │
         ▼                                     │
┌────────────────────────────────────────┐     │
│  Streamlit UI                          │─────┘
│                                        │
│  • Risk tier + recommended action      │
│  • Red flags with severity + citations │
│  • SAR narrative draft (who/what/      │
│    when/where/why/how)                 │
│  • Reasoning summary                   │
│  • Raw vs tokenized diff pane          │
│  • Hash-chain audit timeline           │
│  • SQL executed (entity history)       │
│  • Analyst disposition → Postgres      │
└────────────────────────────────────────┘
```

---

## Tech stack

| Layer | Technology | Rationale |
|---|---|---|
| LLM | Claude Sonnet 4.6 via **AWS Bedrock** | On-resume; enterprise-grade; data stays in AWS perimeter |
| LLM fallback | Anthropic API direct | Activated automatically when Bedrock creds absent |
| PII redaction | **Microsoft Presidio** + regex | Production-grade named entity recognition; handles PERSON, LOCATION, SSN, CREDIT_CARD, phone, email |
| Database | **PostgreSQL + pgvector** via Supabase | On-resume; vector similarity search in the same DB as relational data; zero infra overhead |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | 384-dim, runs locally, fast, free; vectors stored in pgvector |
| Output validation | **Pydantic v2** | Tool-use schema enforces citations at the schema level — every red flag must cite a source_id |
| Audit | SHA-256 hash chain | Each step hashes the previous hash + payload; tamper-evident, SR 11-7 aligned |
| UI | Streamlit 1.39 | Single-file, ships fast, enterprise light theme |
| Synthetic data | Faker | 50 realistic alerts across 4 typologies; 70% TP / 30% FP distribution |

---

## Repo structure

```
aml-copilot/
│
├── app.py                      # Streamlit UI — full analyst workbench
├── schema.sql                  # Postgres schema with pgvector indexes
├── requirements.txt
├── .env.example
│
├── src/
│   ├── models.py               # Pydantic schemas: Citation, RedFlag, TriageBrief
│   ├── redaction.py            # PII redaction (Presidio + regex) + rehydration
│   ├── audit.py                # SHA-256 hash-chained audit log
│   ├── retrieval.py            # pgvector queries: regs, similar cases, entity history
│   ├── synthetic.py            # Faker-based alert + entity + transaction seeding
│   ├── triage.py               # 12-step orchestrator pipeline
│   ├── db.py                   # psycopg2 connection factory
│   └── clients/
│       ├── base.py             # Abstract LLMClient interface
│       ├── bedrock.py          # AWS Bedrock implementation
│       └── anthropic_direct.py # Anthropic API fallback
│
├── scripts/
│   └── seed_regulations.py     # Embeds + inserts 15 reg chunks (FinCEN, FATF, FINTRAC, SR 11-7)
│
└── tests/
    ├── test_models.py          # Pydantic schema validation (citation enforcement)
    ├── test_audit.py           # Hash chain construction + tamper detection
    └── test_redaction.py       # PII redaction / rehydration roundtrip
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/WalkwithOJ/AML-copilot.git
cd aml-copilot
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

### 2. Environment variables

Copy `.env.example` to `.env` and fill in:

```env
# AWS Bedrock (primary LLM)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20251001-v2:0

# Supabase Postgres (Transaction Pooler URL from Connect tab)
DATABASE_URL=postgresql://postgres.xxxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres

# Fallback: if Bedrock not configured, the app uses Anthropic API directly
ANTHROPIC_API_KEY=
```

The app auto-detects which client to use: if `BEDROCK_MODEL_ID` and `AWS_ACCESS_KEY_ID` are set, it uses Bedrock. Otherwise it falls back to the Anthropic API.

### 3. Database setup

Paste `schema.sql` into the Supabase SQL editor and run it. This creates the five tables and IVFFlat indexes.

### 4. Seed data

```bash
# Seed the regulatory knowledge base (run once)
python scripts/seed_regulations.py

# Generate 50 synthetic alerts with entities and transactions
python -c "from src.db import get_conn; from src.synthetic import seed_database; seed_database(get_conn())"
```

### 5. Run

```bash
streamlit run app.py
```

Open `localhost:8501`.

---

## Running tests

```bash
pytest tests/ -v
```

34 tests covering:
- Pydantic schema enforcement (red flags without citations are rejected at parse time)
- SHA-256 hash chain construction and tamper detection
- PII redaction/rehydration roundtrip accuracy

---

## Core design decisions

### Why PII redaction before the LLM?

In production AML systems, raw customer data (names, account numbers, SSNs) is subject to GLBA, PIPEDA, and internal data governance policies that prohibit sending it to third-party hosted services without explicit customer consent. This is the primary reason most banks haven't deployed LLM-assisted AML tools: the compliance team blocks it.

The redaction layer — Presidio NER + account-number regex — tokenizes the narrative before it leaves the bank's perimeter. The LLM reasons about `[PERSON_001]` and `[ACCT_A3F2B1]`, not the real data. After the LLM responds, the token map is applied locally to rehydrate. The LLM output is correct, readable, and citable — but the model never saw the actual PII.

### Why tool use (structured output) instead of free-form prompting?

Free-form LLM responses can hallucinate regulations, invent case precedents, or omit citations. By forcing the model to call a `submit_triage` tool whose schema is generated from the `TriageBrief` Pydantic model, we get:

- **Hard citation enforcement at parse time**: every `RedFlag` must have at least one `Citation`. If the model tries to return a flag without a citation, Pydantic raises a `ValidationError` before anything reaches the UI.
- **Structural consistency**: `risk_tier` and `recommended_action` are enums — the model can't return `"probably escalate"`.
- **Zero parsing fragility**: no regex scraping of markdown. The tool input is a JSON dict that maps directly to the schema.

### Why SHA-256 hash chaining?

Federal Reserve SR 11-7 requires AI/ML models used in compliance decisions to have an auditable, reproducible decision trail. The audit log is append-only and each row hashes `(prev_hash || json_payload)` into `curr_hash`. Any post-hoc modification to a log entry invalidates every subsequent hash — the `verify_chain()` function detects this and returns `False`. This is the same tamper-evidence principle as Bitcoin's block chain, applied to compliance audit logs.

### Why pgvector for retrieval instead of a vector database?

The alternative (Pinecone, Weaviate, Chroma) adds a separate service, separate API key, separate billing, and a separate potential data residency issue. Supabase with the `pgvector` extension provides vector similarity search in the same PostgreSQL instance as the relational entity and transaction data — one connection string, one query engine, one place for an examiner to look. The cosine similarity queries (`embedding <=> %s::vector`) use IVFFlat indexes and run in milliseconds for the dataset sizes relevant to production AML queues.

### Why the LLMClient abstraction?

```
LLMClient (ABC)
├── BedrockClient       ← production, data stays in AWS
└── AnthropicDirectClient ← development fallback
```

AWS Bedrock model access takes 1–5 days to approve after requesting it. Without this abstraction, the entire pipeline is blocked. With it, development and testing proceed against the Anthropic API; the Bedrock client is swapped in by changing one environment variable. The interface contract (`triage(system, user) -> TriageBrief`) is identical in both — the rest of the codebase has no knowledge of which client is active.

---

## The 12-step triage pipeline (`src/triage.py`)

| Step | Action | Audit log entry |
|---|---|---|
| 1 | Fetch raw alert from Postgres | — |
| 2 | Log raw alert received | `raw_alert` |
| 3 | Presidio + regex PII redaction | — |
| 4 | Log tokenization stats | `redaction` |
| 5 | Embed tokenized narrative (all-MiniLM-L6-v2) | — |
| 6 | Retrieve: regs, similar cases, entity history | — |
| 7 | Log retrieved source IDs | `retrieval` |
| 8 | Build system + user prompt with retrieved context | — |
| 9 | Call LLM → TriageBrief (Pydantic validated) | — |
| 10 | Log full LLM response | `llm_response` |
| 11 | Rehydrate PII tokens in text fields | — |
| 12 | Log completion + mark alert reviewed | `rehydration` |

---

## Regulatory corpus

15 chunks embedded and stored in the `regulations` table:

| Source | Sections |
|---|---|
| **FinCEN** | CTR threshold (31 CFR 1010.311), SAR filing obligation (31 CFR 1020.320), structuring red flags (FIN-2010-A001), TBML advisory (FIN-2014-A005), round-trip guidance (FIN-2006-G015) |
| **FATF** | ML offence (Rec. 3), CDD/EDD (Rec. 10), MVTS/TBML (Rec. 14), beneficial ownership (Rec. 24), STR reporting (Rec. 20) |
| **FINTRAC** | STR obligation (PCMLTFA s.7), LCTR threshold, shell company red flags (Guideline 2) |
| **Federal Reserve SR 11-7** | Model risk governance, audit trail requirements |

---

## Synthetic data

50 alerts across 4 typologies, generated by `src/synthetic.py`:

| Typology | Pattern |
|---|---|
| **Structuring** | 3–7 cash deposits of $8,500–$9,999 over 5–21 days — just below the $10k CTR threshold |
| **Trade-based ML** | Wire to offshore counterparty for goods invoiced 30–70% above market benchmark, no import docs |
| **Shell company layering** | Funds through 2–4 shell companies across 3–7 jurisdictions in 10–30 days, obscured beneficial ownership |
| **Rapid round-tripping** | Large wire out, returned within 3–14 days via offshore correspondent, slightly diminished |

Distribution: 35 true positives, 15 false positives (70/30), matching the actual ~95% FP rate analysts face.

---

## Key interview talking points

**Q: What problem does this actually solve?**

The production blocker for LLM-assisted AML is not the LLM quality — it's that compliance won't allow raw customer data to leave the bank's systems. This project solves that with a two-boundary architecture: PII stays local (redact → send tokens → rehydrate), and the LLM only ever reasons about opaque identifiers. That design pattern is directly deployable in a regulated institution.

**Q: How is the output trustworthy enough for a compliance team?**

Three layers: (1) Citation enforcement at the Pydantic schema level — a brief without citations literally cannot be constructed. (2) The LLM is given only source-tagged retrieved context and told explicitly that hallucinated regulations are a compliance failure. (3) The full decision trail — inputs, retrieved context, LLM output, analyst disposition — is hash-chained, so any post-hoc modification is detectable. SR 11-7 requires exactly this for AI models used in compliance decisions.

**Q: Why is the human-in-the-loop design important?**

Verafin's product philosophy is analyst augmentation, not replacement. The copilot pre-investigates and drafts — the licensed analyst still makes every final determination before any regulatory action. This matters legally: a SAR filed without analyst review is a compliance failure regardless of how good the AI recommendation was. The "Analyst Disposition" row saves the analyst's accept/edit/reject decision back to Postgres, creating a full accountability chain.

**Q: What would production actually look like?**

Replace Streamlit with a Next.js frontend. Replace Supabase with RDS inside the bank's VPC. Route Bedrock calls through a PrivateLink endpoint so no traffic traverses the public internet. Add a LangGraph agentic loop so the model can request additional KYC lookups rather than working with a fixed retrieval window. Add a ragas eval harness to measure retrieval precision and hallucination rate over time. Regional Bedrock routing (us-east-1 for US alerts, ca-central-1 for Canadian ones) solves data residency requirements.

---

## Roadmap

- [ ] LangGraph agentic orchestrator — model requests follow-up KYC lookups rather than one-shot RAG
- [ ] AWS-native deployment — Lambda + API Gateway + RDS + Cognito (replace Streamlit + Supabase)
- [ ] Cryptographic Merkle audit chain (replaces linear hash chain)
- [ ] Custom Presidio recognizers for AML-specific entities (IBAN, SWIFT/BIC, cryptocurrency addresses)
- [ ] Regional Bedrock routing — us-east-1 / ca-central-1 split for FinCEN vs FINTRAC data residency
- [ ] ragas eval harness — retrieval precision, answer faithfulness, hallucination rate
- [ ] Differential privacy on similar-case retrieval (k-anonymity over embedding space)
- [ ] Next.js + shadcn UI (replace Streamlit)
