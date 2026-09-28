"""WebSocket tests (required checks 10, 11 and 16)."""

import json

from fastapi.testclient import TestClient


def _drain_until(websocket, expected_type: str, limit: int = 12) -> dict:
    """Read messages until one of ``expected_type`` arrives."""
    for _ in range(limit):
        message = websocket.receive_json()
        if message.get("type") == expected_type:
            return message
    raise AssertionError(f"No {expected_type} event received within {limit} messages.")


def test_websocket_connection_receives_connected_session_event(
    client: TestClient, session_id: str
) -> None:
    with client.websocket_connect(f"/ws/session/{session_id}") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "session"
        assert message["sessionId"] == session_id
        assert message["status"] == "connected"


def test_websocket_connection_updates_session_state(
    client: TestClient, session_id: str
) -> None:
    with client.websocket_connect(f"/ws/session/{session_id}"):
        state = client.get(f"/session/{session_id}").json()
        assert state["connectedClients"] == 1
        assert state["status"] == "connected"


def test_websocket_disconnect_cleans_up_registry(
    client: TestClient, session_id: str
) -> None:
    with client.websocket_connect(f"/ws/session/{session_id}"):
        assert client.get("/health").json()["websocketClients"] == 1

    assert client.get("/health").json()["websocketClients"] == 0
    assert client.get(f"/session/{session_id}").json()["connectedClients"] == 0


def test_backend_survives_client_disconnect_and_accepts_reconnect(
    client: TestClient, session_id: str
) -> None:
    for _ in range(3):
        with client.websocket_connect(f"/ws/session/{session_id}"):
            assert client.get("/health").json()["websocketClients"] == 1

    # The server is still healthy and the session is still usable.
    assert client.get("/health").json()["status"] == "ok"
    assert client.get(f"/session/{session_id}").status_code == 200


def test_websocket_to_unknown_session_returns_structured_error(client: TestClient) -> None:
    with client.websocket_connect("/ws/session/session_999") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "error"
        assert message["code"] == "SESSION_NOT_FOUND"
        assert message["recoverable"] is False


def test_websocket_broadcasts_transcript_claim_and_verification(
    client: TestClient, session_id: str
) -> None:
    with client.websocket_connect(f"/ws/session/{session_id}") as websocket:
        _drain_until(websocket, "session")

        response = client.post(
            "/events/transcript",
            json={
                "type": "transcript",
                "sessionId": session_id,
                "speaker": "Speaker 1",
                "text": "India won the 2011 Cricket World Cup.",
                "timestamp": 12.4,
                "isFinal": True,
            },
        )
        assert response.status_code == 202

        seen = {}
        for _ in range(3):
            message = websocket.receive_json()
            seen.setdefault(message["type"], message)

        assert seen["transcript"]["text"] == "India won the 2011 Cricket World Cup."
        assert seen["claim"]["claimId"] == "claim_001"
        assert seen["verification"]["claimId"] == "claim_001"
        assert seen["verification"]["verdict"] == "TRUE"


def test_websocket_broadcasts_unverifiable_for_unknown_claim(
    client: TestClient, session_id: str
) -> None:
    """A claim the mock verifier has no rule for yields UNVERIFIABLE, not an error.

    The offline mock cannot invent evidence, so an unknown claim is an honest
    verdict. A `VERIFICATION_FAILED` error event is reserved for a real engine
    failure (see test_websocket.py's sibling coverage in test_idempotency.py).
    """
    with client.websocket_connect(f"/ws/session/{session_id}") as websocket:
        _drain_until(websocket, "session")

        response = client.post(
            "/events/claim",
            json={
                "type": "claim",
                "claimId": "claim_unknown_01",
                "sessionId": session_id,
                "speaker": "Speaker 2",
                "timestamp": 5.0,
                "claim": "An entirely unlisted assertion with no rule.",
                "claimType": "statistic",
            },
        )
        assert response.status_code == 202
        body = response.json()
        assert body["counts"]["errors"] == 0
        assert len(body["verifications"]) == 1
        assert body["verifications"][0]["verdict"] == "UNVERIFIABLE"

        message = _drain_until(websocket, "verification")
        assert message["claimId"] == "claim_unknown_01"
        assert message["sessionId"] == session_id
        assert message["verdict"] == "UNVERIFIABLE"
        assert message["source"]


def test_websocket_ping_pong(client: TestClient, session_id: str) -> None:
    with client.websocket_connect(f"/ws/session/{session_id}") as websocket:
        _drain_until(websocket, "session")
        websocket.send_text(json.dumps({"type": "ping"}))
        assert _drain_until(websocket, "pong")["sessionId"] == session_id


def test_websocket_malformed_client_message_returns_error_event(
    client: TestClient, session_id: str
) -> None:
    with client.websocket_connect(f"/ws/session/{session_id}") as websocket:
        _drain_until(websocket, "session")
        websocket.send_text("this is not json")
        message = _drain_until(websocket, "error")
        assert message["code"] == "MALFORMED_EVENT"


def test_websocket_broadcasts_to_multiple_clients(
    client: TestClient, session_id: str
) -> None:
    with client.websocket_connect(f"/ws/session/{session_id}") as first:
        _drain_until(first, "session")
        with client.websocket_connect(f"/ws/session/{session_id}") as second:
            _drain_until(second, "session")
            assert client.get("/health").json()["websocketClients"] == 2

            client.post(
                "/events/verification",
                json={
                    "type": "verification",
                    "claimId": "claim_001",
                    "sessionId": session_id,
                    "speaker": "Speaker 1",
                    "timestamp": 12.4,
                    "verdict": "FALSE",
                    "reason": "Mocked external verification result.",
                    "source": "https://example.com/source",
                },
            )

            for socket in (first, second):
                message = _drain_until(socket, "verification")
                assert message["claimId"] == "claim_001"
                assert message["verdict"] == "FALSE"


def test_stopping_session_closes_websocket_clients(
    client: TestClient, session_id: str
) -> None:
    with client.websocket_connect(f"/ws/session/{session_id}") as websocket:
        _drain_until(websocket, "session")
        response = client.post("/session/stop", params={"sessionId": session_id})
        assert response.status_code == 200

    assert client.get("/health").json()["websocketClients"] == 0
