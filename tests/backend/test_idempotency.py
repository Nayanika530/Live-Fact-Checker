"""Exactly-once semantics: one claimId yields one verification per session.

The failure this replaces was visible in a normal demo run: two of the four
mock segments resolve to the same claim text, so a naive pipeline verified the
same claimId twice and the UI showed it twice. Idempotency is keyed on
``(sessionId, claimId)``, so the same claimId in two different sessions is
still verified in each of them.
"""

import threading
import time

from fastapi.testclient import TestClient

from tests.backend.conftest import (
    claim_payload,
    transcript_payload,
    verification_payload,
)


def _drain_until(websocket, expected_type: str, limit: int = 12) -> dict:
    """Read messages until one of ``expected_type`` arrives."""
    for _ in range(limit):
        message = websocket.receive_json()
        if message.get("type") == expected_type:
            return message
    raise AssertionError(f"No {expected_type} event received within {limit} messages.")


def _collect_for(websocket, seconds: float = 0.5) -> list[dict]:
    """Read WebSocket messages for a fixed window, then stop.

    ``receive_json`` blocks, so a reader thread with a deadline is the only way to
    assert that *no* further message arrives. This is what proves a duplicate was
    not re-broadcast, rather than just proving the first one was.
    """
    messages: list[dict] = []
    stop = threading.Event()

    def reader() -> None:
        while not stop.is_set():
            try:
                messages.append(websocket.receive_json())
            except Exception:  # noqa: BLE001 - the socket closed or read timed out
                return

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    time.sleep(seconds)
    stop.set()
    thread.join(timeout=1.0)
    return messages


def _post_claim(client: TestClient, session_id: str, **overrides) -> dict:
    payload = claim_payload(session_id, **overrides)
    response = client.post("/events/claim", json=payload)
    assert response.status_code == 202
    return response.json()


def test_duplicate_claim_is_not_verified_twice(
    client: TestClient, session_id: str
) -> None:
    first = _post_claim(client, session_id)
    assert first["idempotent"] is False
    assert first["counts"]["claims"] == 1
    assert len(first["verifications"]) == 1
    first_verification = first["verifications"][0]

    second = _post_claim(client, session_id)
    assert second["idempotent"] is True
    assert second["counts"]["claims"] == 0
    # The original result is returned, so a client that retried still gets an answer.
    assert second["verifications"] == [first_verification]


def test_duplicate_claim_does_not_increment_counters(
    client: TestClient, session_id: str
) -> None:
    _post_claim(client, session_id)
    before = client.get(f"/session/{session_id}").json()
    _post_claim(client, session_id)
    after = client.get(f"/session/{session_id}").json()

    assert after["claimCount"] == before["claimCount"] == 1
    assert after["verificationCount"] == before["verificationCount"] == 1


def test_duplicate_claim_is_broadcast_only_once(
    client: TestClient, session_id: str
) -> None:
    """Three posts of the same claimId reach the frontend exactly once."""
    payload = claim_payload(session_id)
    with client.websocket_connect(f"/ws/session/{session_id}") as websocket:
        _drain_until(websocket, "session")

        for _ in range(3):
            client.post("/events/claim", json=payload)

        messages = _collect_for(websocket)

    claims = [m for m in messages if m["type"] == "claim"]
    verifications = [m for m in messages if m["type"] == "verification"]
    assert len(claims) == 1
    assert len(verifications) == 1
    assert claims[0]["claimId"] == verifications[0]["claimId"]


def test_duplicate_verification_post_keeps_the_first_result(
    client: TestClient, session_id: str
) -> None:
    first = client.post(
        "/events/verification", json=verification_payload(session_id, verdict="TRUE")
    )
    assert first.status_code == 202
    assert first.json()["idempotent"] is False
    assert first.json()["broadcastTo"] == 0  # no websocket attached

    second = client.post(
        "/events/verification",
        json=verification_payload(session_id, verdict="FALSE", reason="contradicted"),
    )
    assert second.status_code == 202
    body = second.json()
    assert body["idempotent"] is True
    assert body["verification"]["verdict"] == "TRUE"
    assert body["broadcastTo"] == 0

    # The count reflects one verification, not two.
    assert client.get(f"/session/{session_id}").json()["verificationCount"] == 1


def test_duplicate_verification_post_is_broadcast_only_once(
    client: TestClient, session_id: str
) -> None:
    with client.websocket_connect(f"/ws/session/{session_id}") as websocket:
        while True:
            if websocket.receive_json()["type"] == "session":
                break

        payload = verification_payload(session_id, verdict="TRUE")
        first = client.post("/events/verification", json=payload).json()
        second = client.post("/events/verification", json=payload).json()

        assert first["broadcastTo"] == 1
        assert second["broadcastTo"] == 0

        messages = _collect_for(websocket)

    broadcasts = [m for m in messages if m["type"] == "verification"]
    assert len(broadcasts) == 1
    assert broadcasts[0]["verdict"] == "TRUE"


def test_claim_posted_after_a_duplicate_transcript_is_idempotent(
    client: TestClient, session_id: str
) -> None:
    """`/events/claim` shares the registry with `/events/transcript`."""
    transcript = client.post(
        "/events/transcript", json=transcript_payload(session_id)
    ).json()
    claim = transcript["claims"][0]
    assert transcript["counts"]["claims"] == 1

    replay = client.post("/events/claim", json=claim)
    assert replay.status_code == 202
    assert replay.json()["idempotent"] is True
    assert replay.json()["counts"]["claims"] == 0
    assert replay.json()["verifications"] == transcript["verifications"]


def test_same_claim_id_in_two_sessions_is_verified_in_both(
    client: TestClient,
) -> None:
    first = client.post("/session/start", json={}).json()["sessionId"]
    second = client.post("/session/start", json={}).json()["sessionId"]
    assert first != second

    first_body = _post_claim(client, first)
    second_body = _post_claim(client, second)

    assert first_body["idempotent"] is False
    assert second_body["idempotent"] is False
    assert len(second_body["verifications"]) == 1
    assert second_body["verifications"][0]["sessionId"] == second
    assert first_body["verifications"][0]["sessionId"] == first


def test_mock_pipeline_verifies_every_distinct_claim(
    client: TestClient,
) -> None:
    """The shipped script runs end to end with no errors and no double counting.

    The script's 3 segments yield 2 claims (the greeting has none), and each is
    verified exactly once. Duplicate suppression itself is covered above.
    """
    from backend.mocks.mock_stream import MOCK_TRANSCRIPT_SCRIPT

    session = client.post(
        "/session/start", json={"startMockPipeline": True}
    ).json()["sessionId"]

    expected_transcripts = len(MOCK_TRANSCRIPT_SCRIPT)
    stats = client.get(f"/session/{session}").json()
    deadline = time.monotonic() + 15.0
    while stats["transcriptCount"] < expected_transcripts and time.monotonic() < deadline:
        time.sleep(0.1)
        stats = client.get(f"/session/{session}").json()
    client.post("/session/stop", params={"sessionId": session})

    assert stats["transcriptCount"] == expected_transcripts
    assert stats["claimCount"] == stats["verificationCount"] == 2
    assert stats["errorCount"] == 0
