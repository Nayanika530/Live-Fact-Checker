"""Event ingestion and validation tests (required checks 6, 7, 8, 9 and 15)."""

import pytest
from fastapi.testclient import TestClient

from tests.backend.conftest import (
    claim_payload,
    transcript_payload,
    verification_payload,
)

VALID_VERDICTS = ["TRUE", "FALSE", "UNVERIFIABLE"]


# ---------------------------------------------------------------------------
# Transcript validation
# ---------------------------------------------------------------------------

def test_transcript_accepted(client: TestClient, session_id: str) -> None:
    response = client.post("/events/transcript", json=transcript_payload(session_id))
    assert response.status_code == 202

    body = response.json()
    assert body["accepted"] is True
    assert body["sessionId"] == session_id
    assert body["transcript"]["type"] == "transcript"
    assert body["transcript"]["isFinal"] is True


@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param({"text": ""}, id="empty_text"),
        pytest.param({"text": "   "}, id="whitespace_text"),
        pytest.param({"timestamp": -1.0}, id="negative_timestamp"),
        pytest.param({"sessionId": ""}, id="empty_session_id"),
    ],
)
def test_transcript_validation_rejects_bad_payload(
    client: TestClient, session_id: str, invalid: dict
) -> None:
    response = client.post(
        "/events/transcript", json=transcript_payload(session_id, **invalid)
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SCHEMA_VALIDATION_FAILED"


def test_transcript_requires_text_field(client: TestClient, session_id: str) -> None:
    payload = transcript_payload(session_id)
    del payload["text"]
    response = client.post("/events/transcript", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Claim validation
# ---------------------------------------------------------------------------

def test_claim_accepted_and_verified(client: TestClient, session_id: str) -> None:
    response = client.post("/events/claim", json=claim_payload(session_id))
    assert response.status_code == 202

    body = response.json()
    assert body["accepted"] is True
    assert body["claim"]["claimId"] == "claim_001"
    assert len(body["verifications"]) == 1
    assert body["verifications"][0]["verdict"] == "TRUE"


@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param({"claimId": ""}, id="empty_claim_id"),
        pytest.param({"claim": ""}, id="empty_claim"),
        pytest.param({"claim": "   "}, id="whitespace_claim"),
        pytest.param({"timestamp": -0.5}, id="negative_timestamp"),
        pytest.param({"sessionId": ""}, id="empty_session_id"),
    ],
)
def test_claim_validation_rejects_bad_payload(
    client: TestClient, session_id: str, invalid: dict
) -> None:
    response = client.post("/events/claim", json=claim_payload(session_id, **invalid))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SCHEMA_VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# Verification validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("verdict", VALID_VERDICTS)
def test_verification_accepts_allowed_verdicts(
    client: TestClient, session_id: str, verdict: str
) -> None:
    response = client.post(
        "/events/verification",
        json=verification_payload(session_id, verdict=verdict),
    )
    assert response.status_code == 202
    assert response.json()["verification"]["verdict"] == verdict


@pytest.mark.parametrize(
    "verdict",
    ["True", "False", "Unverifiable", "true", "false", "unverifiable", "MAYBE", ""],
)
def test_invalid_verdict_is_rejected(
    client: TestClient, session_id: str, verdict: str
) -> None:
    """Only uppercase TRUE / FALSE / UNVERIFIABLE are valid on the wire."""
    response = client.post(
        "/events/verification",
        json=verification_payload(session_id, verdict=verdict),
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SCHEMA_VALIDATION_FAILED"


@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param({"reason": ""}, id="empty_reason"),
        pytest.param({"source": ""}, id="empty_source"),
        pytest.param({"claimId": ""}, id="empty_claim_id"),
    ],
)
def test_verification_validation_rejects_bad_payload(
    client: TestClient, session_id: str, invalid: dict
) -> None:
    response = client.post(
        "/events/verification", json=verification_payload(session_id, **invalid)
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Malformed events
# ---------------------------------------------------------------------------

def test_malformed_json_body_is_rejected(client: TestClient, session_id: str) -> None:
    response = client.post(
        "/events/transcript",
        content="{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "MALFORMED_EVENT"


def test_non_object_json_body_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/events/transcript", content="[1,2,3]", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400


def test_wrong_event_type_is_rejected(client: TestClient, session_id: str) -> None:
    response = client.post(
        "/events/transcript", json=transcript_payload(session_id, type="claim")
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSUPPORTED_EVENT_TYPE"


def test_event_for_unknown_session_returns_404(client: TestClient) -> None:
    response = client.post("/events/transcript", json=transcript_payload("session_999"))
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "SESSION_NOT_FOUND"


def test_unknown_fields_are_ignored_not_rejected(
    client: TestClient, session_id: str
) -> None:
    """Forward compatibility: an extra field must not break the live demo."""
    response = client.post(
        "/events/transcript",
        json=transcript_payload(session_id, someFutureField="value"),
    )
    assert response.status_code == 202
