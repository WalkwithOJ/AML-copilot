"""pgvector-backed retrieval: entity history, regulation search, similar case search."""
from sentence_transformers import SentenceTransformer

_model = None


def _embedder():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text: str) -> list[float]:
    return _embedder().encode(text).tolist()


# ---------------------------------------------------------------------------
# Entity history
# ---------------------------------------------------------------------------

ENTITY_HISTORY_SQL = """
SELECT
    e.name,
    e.entity_type,
    e.country,
    e.risk_score,
    t.amount,
    t.currency,
    t.txn_type,
    t.occurred_at,
    r.name AS counterparty
FROM entities e
JOIN transactions t ON (t.sender_id = e.id OR t.receiver_id = e.id)
JOIN entities r ON (CASE WHEN t.sender_id = e.id THEN t.receiver_id ELSE t.sender_id END = r.id)
WHERE e.id = %s
ORDER BY t.occurred_at DESC
LIMIT 20
"""


def get_entity_history(conn, entity_id: int) -> tuple[str, str]:
    """Returns (formatted_text, sql_used) for display and audit."""
    with conn.cursor() as cur:
        cur.execute(ENTITY_HISTORY_SQL, (entity_id,))
        rows = cur.fetchall()

    if not rows:
        return "No prior transaction history found.", ENTITY_HISTORY_SQL

    name, etype, country, risk = rows[0][0], rows[0][1], rows[0][2], rows[0][3]
    lines = [
        f"Entity: {name} ({etype}), Country: {country}, Risk Score: {risk}",
        "--- Transaction History (most recent 20) ---",
    ]
    for _, _, _, _, amount, currency, txn_type, occurred_at, counterparty in rows:
        lines.append(
            f"  {occurred_at.strftime('%Y-%m-%d')}: {currency} {amount:,.2f} "
            f"[{txn_type}] with {counterparty}"
        )
    return "\n".join(lines), ENTITY_HISTORY_SQL


# ---------------------------------------------------------------------------
# Regulation search
# ---------------------------------------------------------------------------

def search_regulations(conn, query_text: str, top_k: int = 3) -> list[dict]:
    """Cosine similarity search over regulations table."""
    qvec = embed(query_text)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source, section, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM regulations
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (qvec, qvec, top_k),
        )
        rows = cur.fetchall()
    return [
        {
            "id": f"reg_{r[0]}",
            "source": r[1],
            "section": r[2],
            "content": r[3],
            "similarity": float(r[4]),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Similar case search
# ---------------------------------------------------------------------------

def find_similar_cases(conn, alert_id: int, alert_embedding: list[float], top_k: int = 3) -> list[dict]:
    """Cosine similarity search over alerts, excluding self."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, typology, raw_narrative, ground_truth,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM alerts
            WHERE id != %s AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (alert_embedding, alert_id, alert_embedding, top_k),
        )
        rows = cur.fetchall()
    return [
        {
            "id": f"case_{r[0]}",
            "source": f"Past Alert #{r[0]} ({r[1]})",
            "content": f"[{r[3] or 'unknown'}] {r[2][:300]}...",
            "similarity": float(r[4]),
        }
        for r in rows
    ]
