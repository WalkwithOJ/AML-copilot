import pytest
from unittest.mock import MagicMock, call
from src.audit import hash_payload, log_step, verify_chain


class TestHashPayload:
    def test_deterministic(self):
        h1 = hash_payload("abc", {"key": "value"})
        h2 = hash_payload("abc", {"key": "value"})
        assert h1 == h2

    def test_genesis_block(self):
        h = hash_payload(None, {"step": "start"})
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_different_prev_hash_changes_result(self):
        h1 = hash_payload("aaa", {"key": "value"})
        h2 = hash_payload("bbb", {"key": "value"})
        assert h1 != h2

    def test_different_payload_changes_result(self):
        h1 = hash_payload("prev", {"a": 1})
        h2 = hash_payload("prev", {"a": 2})
        assert h1 != h2

    def test_key_order_independent(self):
        h1 = hash_payload("prev", {"b": 2, "a": 1})
        h2 = hash_payload("prev", {"a": 1, "b": 2})
        assert h1 == h2


class TestLogStep:
    def _make_conn(self, prev_hash=None):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = (prev_hash,) if prev_hash else None
        return conn, cur

    def test_inserts_audit_row(self):
        conn, cur = self._make_conn()
        result = log_step(conn, alert_id=1, step="raw_alert", payload={"n": 100})
        assert isinstance(result, str)
        assert len(result) == 64
        conn.commit.assert_called_once()

    def test_uses_genesis_when_no_prior_hash(self):
        conn, cur = self._make_conn(prev_hash=None)
        h = log_step(conn, 1, "start", {})
        expected = hash_payload(None, {})
        assert h == expected

    def test_chains_from_previous_hash(self):
        conn, cur = self._make_conn(prev_hash="abc123")
        h = log_step(conn, 1, "step2", {"x": 1})
        expected = hash_payload("abc123", {"x": 1})
        assert h == expected


class TestVerifyChain:
    def _make_conn_with_rows(self, rows):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchall.return_value = rows
        return conn

    def _build_valid_chain(self, steps):
        rows = []
        prev = None
        for step, payload in steps:
            curr = hash_payload(prev, payload)
            rows.append((step, payload, prev, curr))
            prev = curr
        return rows

    def test_valid_chain_returns_true(self):
        steps = [("raw_alert", {"n": 5}), ("redaction", {"tokens": 3})]
        rows = self._build_valid_chain(steps)
        conn = self._make_conn_with_rows(rows)
        assert verify_chain(conn, alert_id=1) is True

    def test_tampered_hash_returns_false(self):
        steps = [("raw_alert", {"n": 5})]
        rows = self._build_valid_chain(steps)
        tampered = list(rows[0])
        tampered[3] = "0" * 64
        conn = self._make_conn_with_rows([tuple(tampered)])
        assert verify_chain(conn, alert_id=1) is False

    def test_broken_chain_link_returns_false(self):
        steps = [("step1", {"a": 1}), ("step2", {"b": 2})]
        rows = self._build_valid_chain(steps)
        broken = list(rows[1])
        broken[2] = "wrong_prev"
        conn = self._make_conn_with_rows([rows[0], tuple(broken)])
        assert verify_chain(conn, alert_id=1) is False

    def test_empty_chain_returns_true(self):
        conn = self._make_conn_with_rows([])
        assert verify_chain(conn, alert_id=99) is True
