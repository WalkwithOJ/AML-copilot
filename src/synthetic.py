"""Generate ~50 synthetic AML alerts across 4 typologies and seed the database."""
import random
from datetime import datetime, timedelta
from faker import Faker
from sentence_transformers import SentenceTransformer

fake = Faker()
_model = None


def _embedder():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# ---------------------------------------------------------------------------
# Narrative generators per typology
# ---------------------------------------------------------------------------

def _structuring_narrative(sender: str, accts: list[str]) -> str:
    amounts = [random.randint(8_500, 9_999) for _ in range(random.randint(3, 7))]
    txns = ", ".join(f"${a:,}" for a in amounts)
    return (
        f"{sender} made {len(amounts)} cash deposits of {txns} over "
        f"{random.randint(5, 21)} days across accounts "
        f"{', '.join(accts[:2])}. Each deposit fell just below the $10,000 CTR "
        f"threshold. No corresponding business income identified. Total: "
        f"${sum(amounts):,}."
    )


def _trade_based_narrative(sender: str, receiver: str, acct: str) -> str:
    goods = random.choice(["electronics", "textiles", "machinery parts", "chemicals", "luxury goods"])
    country = random.choice(["Malaysia", "UAE", "Panama", "Cyprus", "Hong Kong"])
    over = random.randint(30, 70)
    return (
        f"Wire transfer of ${random.randint(50_000, 500_000):,} from {sender} "
        f"(account {acct}) to {receiver} in {country} for {goods}. "
        f"Invoiced value is approximately {over}% above market benchmark. "
        f"No import documentation provided. Counterparty is a recently registered shell."
    )


def _shell_company_narrative(entity: str, intermediaries: list[str]) -> str:
    hops = " → ".join(intermediaries)
    return (
        f"Funds originating from {entity} were layered through {len(intermediaries)} "
        f"intermediary shell companies ({hops}) across "
        f"{random.randint(3, 7)} jurisdictions in {random.randint(10, 30)} days. "
        f"Beneficial ownership is obscured; no economic activity identified for any entity."
    )


def _round_trip_narrative(entity: str, acct: str) -> str:
    amount = random.randint(100_000, 2_000_000)
    days = random.randint(3, 14)
    return (
        f"${amount:,} transferred out from {entity} (account {acct}) "
        f"and returned within {days} days through correspondent accounts in "
        f"{random.choice(['Cayman Islands', 'British Virgin Islands', 'Liechtenstein', 'Isle of Man'])}. "
        f"Funds returned slightly diminished, suggesting fee payment to obscure origin."
    )


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

TYPOLOGIES = ["structuring", "trade_based_ml", "shell_company_layering", "rapid_round_trip"]

# 35 true positives, 15 false positives
GROUND_TRUTH_DIST = ["true_positive"] * 35 + ["false_positive"] * 15


def seed_database(conn, n: int = 50) -> list[int]:
    """Insert synthetic entities, transactions, and alerts. Returns list of alert IDs."""
    embedder = _embedder()
    random.shuffle(GROUND_TRUTH_DIST)
    ground_truths = GROUND_TRUTH_DIST[:n]
    alert_ids = []

    with conn.cursor() as cur:
        for i in range(n):
            typology = TYPOLOGIES[i % len(TYPOLOGIES)]
            gt = ground_truths[i]

            # Create sender entity
            sender_name = fake.name()
            sender_ext_id = f"ENT_{fake.unique.bothify('??####').upper()}"
            risk = random.randint(60, 95) if gt == "true_positive" else random.randint(10, 40)
            cur.execute(
                "INSERT INTO entities (external_id, name, entity_type, country, risk_score) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (external_id) DO NOTHING RETURNING id",
                (sender_ext_id, sender_name, "individual", fake.country_code(), risk),
            )
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT id FROM entities WHERE external_id=%s", (sender_ext_id,))
                row = cur.fetchone()
            sender_id = row[0]

            # Create receiver entity
            receiver_name = fake.company()
            receiver_ext_id = f"ENT_{fake.unique.bothify('??####').upper()}"
            cur.execute(
                "INSERT INTO entities (external_id, name, entity_type, country, risk_score) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (external_id) DO NOTHING RETURNING id",
                (receiver_ext_id, receiver_name, "business", fake.country_code(), random.randint(20, 80)),
            )
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT id FROM entities WHERE external_id=%s", (receiver_ext_id,))
                row = cur.fetchone()
            receiver_id = row[0]

            # Create transaction
            amount = random.uniform(8_000, 500_000)
            occurred_at = datetime.utcnow() - timedelta(days=random.randint(1, 365))
            cur.execute(
                "INSERT INTO transactions (sender_id, receiver_id, amount, currency, txn_type, occurred_at) "
                "VALUES (%s,%s,%s,'USD',%s,%s) RETURNING id",
                (sender_id, receiver_id, round(amount, 2), typology, occurred_at),
            )
            txn_id = cur.fetchone()[0]

            # Build narrative
            accts = [fake.bothify("########??").upper() for _ in range(3)]
            intermediaries = [fake.company() for _ in range(random.randint(2, 4))]

            if typology == "structuring":
                narrative = _structuring_narrative(sender_name, accts)
            elif typology == "trade_based_ml":
                narrative = _trade_based_narrative(sender_name, receiver_name, accts[0])
            elif typology == "shell_company_layering":
                narrative = _shell_company_narrative(sender_name, intermediaries)
            else:
                narrative = _round_trip_narrative(sender_name, accts[0])

            # Embed narrative
            embedding = embedder.encode(narrative).tolist()

            cur.execute(
                "INSERT INTO alerts (transaction_id, typology, raw_narrative, ground_truth, embedding) "
                "VALUES (%s,%s,%s,%s,%s::vector) RETURNING id",
                (txn_id, typology, narrative, gt, embedding),
            )
            alert_ids.append(cur.fetchone()[0])

    conn.commit()
    print(f"Seeded {n} alerts: {GROUND_TRUTH_DIST[:n].count('true_positive')} TP, "
          f"{GROUND_TRUTH_DIST[:n].count('false_positive')} FP")
    return alert_ids
