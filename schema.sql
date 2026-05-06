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
