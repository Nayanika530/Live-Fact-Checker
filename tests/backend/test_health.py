"""Health endpoint tests (required check 2)."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "Live Fact-Checker Backend"
    assert body["environment"] == "test"
    assert body["sessions"] == 0
    assert body["websocketClients"] == 0


def test_health_reports_wired_engines(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["engines"]["claimEngine"] == "mock-claim-engine"
    assert body["engines"]["verificationEngine"] == "mock-verification-engine"


def test_health_never_exposes_secret_values(client: TestClient) -> None:
    """Only the presence of a credential is reported, never its value."""
    body = client.get("/health").json()
    assert body["credentialsConfigured"] == {
        "assemblyai": False,
        "llmGateway": False,
        "search": False,
    }
    serialized = client.get("/health").text
    for forbidden in ("api_key", "apiKey", "api-key", "bearer", "Bearer"):
        assert forbidden not in serialized


def test_health_counts_active_sessions(client: TestClient) -> None:
    client.post("/session/start", json={})
    client.post("/session/start", json={})
    assert client.get("/health").json()["sessions"] == 2
