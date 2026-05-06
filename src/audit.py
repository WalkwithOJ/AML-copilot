import hashlib
import json


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
            "INSERT INTO audit_log (alert_id, step, payload, prev_hash, curr_hash) VALUES (%s,%s,%s,%s,%s)",
            (alert_id, step, json.dumps(payload, default=str), prev, curr),
        )
    conn.commit()
    return curr


def verify_chain(conn, alert_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT step, payload, prev_hash, curr_hash FROM audit_log WHERE alert_id=%s ORDER BY id",
            (alert_id,),
        )
        rows = cur.fetchall()
    expected_prev = None
    for _step, payload, prev_hash, curr_hash in rows:
        if prev_hash != expected_prev:
            return False
        data = json.loads(payload) if isinstance(payload, str) else payload
        if hash_payload(prev_hash, data) != curr_hash:
            return False
        expected_prev = curr_hash
    return True
