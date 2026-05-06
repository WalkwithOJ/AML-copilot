import re
from src.redaction import redact, rehydrate


class TestRedact:
    def test_replaces_person_name(self):
        text = "John Smith deposited $9,000."
        tokenized, token_map = redact(text)
        assert "John Smith" not in tokenized
        assert any("PERSON" in t for t in token_map)

    def test_replaces_account_number(self):
        text = "Account 123456789 was flagged."
        tokenized, token_map = redact(text)
        assert "123456789" not in tokenized
        acct_tokens = [t for t in token_map if t.startswith("[ACCT_")]
        assert len(acct_tokens) == 1

    def test_token_map_contains_original_value(self):
        text = "Account 987654321 belongs to Jane Doe."
        _, token_map = redact(text)
        assert "987654321" in token_map.values()

    def test_empty_string(self):
        tokenized, token_map = redact("")
        assert tokenized == ""
        assert token_map == {}

    def test_no_pii_text_unchanged(self):
        text = "The weather is sunny today with no suspicious activity."
        tokenized, token_map = redact(text)
        assert tokenized == text
        assert token_map == {}

    def test_multiple_account_numbers(self):
        text = "Transfer from 123456789 to 987654321."
        tokenized, token_map = redact(text)
        assert "123456789" not in tokenized
        assert "987654321" not in tokenized
        acct_tokens = [t for t in token_map if t.startswith("[ACCT_")]
        assert len(acct_tokens) == 2

    def test_token_format_for_accounts(self):
        text = "Account 12345678 was used."
        tokenized, _ = redact(text)
        assert re.search(r"\[ACCT_[A-F0-9]{6}\]", tokenized)


class TestRehydrate:
    def test_replaces_token_with_original(self):
        token_map = {"[PERSON_001]": "Jane Doe", "[ACCT_ABC123]": "123456789"}
        text = "[PERSON_001] used account [ACCT_ABC123]."
        result = rehydrate(text, token_map)
        assert result == "Jane Doe used account 123456789."

    def test_empty_token_map(self):
        text = "No tokens here."
        assert rehydrate(text, {}) == text

    def test_round_trip(self):
        original = "John Smith deposited funds from account 123456789."
        tokenized, token_map = redact(original)
        rehydrated = rehydrate(tokenized, token_map)
        assert "John Smith" in rehydrated or "123456789" in rehydrated
