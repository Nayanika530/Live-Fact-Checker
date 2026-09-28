"""Configuration and secret-redaction tests.

These cover two requirements that are easy to claim and easy to get wrong:
credentials must never reach a log sink, and CORS must not degrade to a
wildcard in production.
"""

import io
import logging

import pytest

from backend.config import LOCAL_DEV_ORIGINS, Settings
from backend.logging_config import (
    REDACTED,
    SecretRedactionFilter,
    configure_logging,
    log_trace,
)


class _ExtrasFormatter(logging.Formatter):
    """Appends structured ``extra`` fields so the test can assert on them."""

    _RESERVED = frozenset(
        vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
    ) | {"message", "asctime", "taskName"}

    def format(self, record: logging.LogRecord) -> str:
        base = record.getMessage()
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._RESERVED and not key.startswith("_")
        }
        return f"{base} {extras}" if extras else base


def _emit(message: str, **extra) -> str:
    """Log one record through a redaction filter and return the emitted text."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream=stream)
    handler.setFormatter(_ExtrasFormatter())
    handler.addFilter(SecretRedactionFilter())

    logger = logging.getLogger("live_fact_checker.test")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        logger.info(message, extra=extra)
    finally:
        logger.handlers = []
    return stream.getvalue()


def test_api_key_is_redacted_from_message() -> None:
    output = _emit("connecting with api_key=super-secret-value-1234")
    assert "super-secret-value-1234" not in output
    assert REDACTED in output


def test_bearer_token_is_redacted_from_message() -> None:
    output = _emit("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9abcdefgh")
    assert "eyJhbGciOiJIUzI1NiJ9abcdefgh" not in output


def test_provider_style_key_is_redacted() -> None:
    output = _emit("using sk-proj-abcdefghijklmnop here")
    assert "sk-proj-abcdefghijklmnop" not in output


def test_secret_in_structured_fields_is_redacted() -> None:
    output = _emit("config loaded", config={"assemblyai_api_key": "abcd1234efgh"})
    assert "abcd1234efgh" not in output
    assert REDACTED in output


def test_password_in_url_is_redacted() -> None:
    output = _emit("dialling postgres://admin:hunter2000@db.internal:5432/app")
    assert "hunter2000" not in output


def test_registered_literal_secret_is_redacted() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream=stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    redaction = SecretRedactionFilter()
    redaction.register_secret("a-real-looking-key-value")
    handler.addFilter(redaction)

    logger = logging.getLogger("live_fact_checker.literal")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        logger.info("token is a-real-looking-key-value now")
    finally:
        logger.handlers = []

    assert "a-real-looking-key-value" not in stream.getvalue()


def test_non_secret_fields_survive() -> None:
    output = _emit(
        "event handled", sessionId="session_001", claimId="claim_001", api_key="leak-me-1234"
    )
    assert "session_001" in output
    assert "claim_001" in output
    assert "leak-me-1234" not in output


def test_trace_label_is_preserved() -> None:
    output = _emit("TRANSCRIPT_RECEIVED", trace="TRANSCRIPT_RECEIVED", sessionId="session_001")
    assert "TRANSCRIPT_RECEIVED" in output


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def test_cors_origins_default_to_local_dev_only() -> None:
    settings = Settings(environment="development")
    assert settings.resolved_cors_origins() == LOCAL_DEV_ORIGINS
    assert "*" not in settings.resolved_cors_origins()


def test_cors_origins_parse_from_comma_separated_string() -> None:
    settings = Settings(
        environment="production",
        cors_origins="https://a.example.com, https://b.example.com",
    )
    assert settings.resolved_cors_origins() == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_wildcard_cors_is_rejected_in_production() -> None:
    settings = Settings(environment="production", cors_origins="*")
    with pytest.raises(ValueError, match="not permitted"):
        settings.resolved_cors_origins()


def test_wildcard_cors_is_allowed_in_development() -> None:
    settings = Settings(environment="development", cors_origins="*")
    assert settings.resolved_cors_origins() == ["*"]


def test_credentials_are_only_reported_as_present_or_absent() -> None:
    settings = Settings(
        environment="test",
        assemblyai_api_key="real-key-value-1234",
        llm_gateway_api_key="",
    )
    assert settings.has_assemblyai_key() is True
    assert settings.has_llm_gateway_key() is False
    assert settings.has_search_key() is False
    assert "real-key-value-1234" not in str(settings.model_dump())


def test_configure_logging_is_idempotent() -> None:
    first = configure_logging(level="INFO", json_output=False)
    count_after_first = len(logging.getLogger().handlers)
    second = configure_logging(level="INFO", json_output=False)
    count_after_second = len(logging.getLogger().handlers)
    assert first is second
    assert count_after_first == count_after_second


def test_log_trace_emits_the_label() -> None:
    configure_logging(level="INFO", json_output=False)
    assert log_trace("TRANSCRIPT_RECEIVED", sessionId="session_001") is None
