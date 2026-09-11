"""
Unit tests for Secret Redaction Filter.
"""
from security.redaction import redact_secrets


def test_redact_openai_key_pattern():
    text = "Error occurred using key sk-1234567890abcdef1234567890abcdef on server"
    safe = redact_secrets(text)
    assert "sk-1234567890abcdef1234567890abcdef" not in safe
    assert "[REDACTED_API_KEY]" in safe


def test_redact_gemini_key_pattern():
    text = "Request with AIzaSyAbcdef1234567890abcdef12345678 failed"
    safe = redact_secrets(text)
    assert "AIzaSyAbcdef1234567890abcdef12345678" not in safe
    assert "[REDACTED_API_KEY]" in safe


def test_redact_bearer_token():
    text = "Headers: Authorization: Bearer secret_access_token_123456"
    safe = redact_secrets(text)
    assert "secret_access_token_123456" not in safe
