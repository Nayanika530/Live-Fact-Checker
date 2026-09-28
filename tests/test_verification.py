"""Unit and integration tests for the Verification module.

Validates:
- Valid ClaimEvent inputs
- Strict claimId preservation
- All three verdict types (True, False, Unverifiable)
- Malformed inputs and schema validation
- No evidence scenarios
- Conflicting evidence scenarios
- Empty, whitespace, and numerical claim handling
- Batch processing and mock dataset integrity
"""

import pytest
from pydantic import ValidationError

from verification.checker import VerificationChecker, verify_claim_against_evidence
from verification.models import ClaimEvent, EvidenceItem, VerdictType, VerificationEvent
from verification.query_generator import clean_conversational_text, generate_search_query
from verification.retriever import MockRetriever
from verification.service import VerificationService, verify_claim_event
from verification.mock_data import MOCK_CLAIMS


# ---------------------------------------------------------------------------
# 1. Model & Validation Tests
# ---------------------------------------------------------------------------

def test_claim_event_valid_input():
    """Ensures valid claim input dictionaries parse correctly into ClaimEvent."""
    payload = {
        "type": "claim",
        "claimId": "claim_001",
        "speaker": "Speaker 1",
        "claim": "The company sold two million units.",
        "timestamp": 12.4,
    }
    event = ClaimEvent(**payload)
    assert event.type == "claim"
    assert event.claimId == "claim_001"
    assert event.speaker == "Speaker 1"
    assert event.claim == "The company sold two million units."
    assert event.timestamp == 12.4


@pytest.mark.parametrize(
    "malformed_payload",
    [
        # Missing claim
        {"type": "claim", "claimId": "claim_001", "speaker": "Speaker 1", "timestamp": 12.4},
        # Missing claimId
        {"type": "claim", "speaker": "Speaker 1", "claim": "Valid claim", "timestamp": 12.4},
        # Empty claim
        {"type": "claim", "claimId": "c1", "speaker": "S1", "claim": "", "timestamp": 12.4},
        # Whitespace-only claim
        {"type": "claim", "claimId": "c1", "speaker": "S1", "claim": "   ", "timestamp": 12.4},
        # Wrong type
        {"type": "wrong_type", "claimId": "c1", "speaker": "S1", "claim": "Valid", "timestamp": 12.4},
        # Negative timestamp
        {"type": "claim", "claimId": "c1", "speaker": "S1", "claim": "Valid", "timestamp": -5.0},
        # Extra unexpected fields (forbidden by strict model config)
        {"type": "claim", "claimId": "c1", "speaker": "S1", "claim": "Valid", "timestamp": 1.0, "extra": "field"},
    ],
)
def test_claim_event_malformed_inputs(malformed_payload):
    """Ensures malformed or invalid payloads are rejected with ValidationError."""
    with pytest.raises(ValidationError):
        ClaimEvent(**malformed_payload)


def test_verification_event_valid():
    """Ensures VerificationEvent matches agreed output contract."""
    event = VerificationEvent(
        type="verification",
        claimId="claim_001",
        verdict=VerdictType.FALSE,
        reason="The available source reports a different figure.",
        source="https://example.com",
    )
    dumped = event.model_dump()
    assert dumped["type"] == "verification"
    assert dumped["claimId"] == "claim_001"
    assert dumped["verdict"] == "False"
    assert dumped["reason"] == "The available source reports a different figure."
    assert dumped["source"] == "https://example.com"


def test_verification_event_rejects_invalid_verdict():
    """Ensures verdict accepts only True, False, or Unverifiable."""
    with pytest.raises(ValidationError):
        VerificationEvent(
            type="verification",
            claimId="claim_001",
            verdict="Maybe",  # Invalid
            reason="Uncertain statement",
            source="https://example.com",
        )


# ---------------------------------------------------------------------------
# 2. Query Generation Tests
# ---------------------------------------------------------------------------

def test_query_generator_cleans_speech_artifacts():
    """Ensures conversational prefixes and discourse markers are stripped."""
    raw = "Speaker 1 said that in my opinion the company sold two million units."
    query = generate_search_query(raw)
    assert "Speaker 1 said that" not in query
    assert "in my opinion" not in query
    assert "company sold two million units" in query


def test_query_generator_handles_empty_string():
    """Ensures empty or whitespace strings return empty queries without error."""
    assert generate_search_query("") == ""
    assert generate_search_query("   ") == ""


# ---------------------------------------------------------------------------
# 3. Pipeline & Claim ID Preservation Tests
# ---------------------------------------------------------------------------

def test_claim_id_preservation():
    """Ensures the original claimId is strictly preserved across the pipeline."""
    service = VerificationService()
    test_id = "unique_claim_id_9999"
    claim = {
        "type": "claim",
        "claimId": test_id,
        "speaker": "Speaker 1",
        "claim": "NASA's Apollo 11 landed humans on the Moon in July 1969.",
        "timestamp": 10.0,
    }
    result = service.verify_claim(claim)
    assert result.claimId == test_id


# ---------------------------------------------------------------------------
# 4. Verdict Types Tests (True / False / Unverifiable)
# ---------------------------------------------------------------------------

def test_verdict_true():
    """Tests a clearly true factual claim."""
    service = VerificationService()
    claim = {
        "type": "claim",
        "claimId": "claim_true_01",
        "speaker": "Speaker 2",
        "claim": "NASA's Apollo 11 landed humans on the Moon in July 1969.",
        "timestamp": 20.0,
    }
    result = service.verify_claim(claim)
    assert result.verdict == VerdictType.TRUE
    assert "nasa.gov" in result.source
    assert result.reason != ""


def test_verdict_false_geographical():
    """Tests a clearly false claim."""
    service = VerificationService()
    claim = {
        "type": "claim",
        "claimId": "claim_false_01",
        "speaker": "Speaker 1",
        "claim": "Mount Everest is the highest mountain peak in Africa.",
        "timestamp": 35.0,
    }
    result = service.verify_claim(claim)
    assert result.verdict == VerdictType.FALSE
    assert "britannica.com" in result.source
    assert "contradict" in result.reason.lower() or "source" in result.reason.lower()


def test_verdict_false_numerical_contract_example():
    """Tests the exact sample claim from project specification."""
    service = VerificationService()
    claim = {
        "type": "claim",
        "claimId": "claim_001",
        "speaker": "Speaker 1",
        "claim": "The company sold two million units.",
        "timestamp": 12.4,
    }
    result = service.verify_claim(claim)
    assert result.claimId == "claim_001"
    assert result.verdict == VerdictType.FALSE
    assert "different figure" in result.reason.lower() or "contradictory" in result.reason.lower()
    assert "sec.gov" in result.source


def test_verdict_unverifiable_no_evidence():
    """Tests an unverifiable claim with no matching evidence found."""
    service = VerificationService()
    claim = {
        "type": "claim",
        "claimId": "claim_unverifiable_01",
        "speaker": "Speaker 3",
        "claim": "The CEO privately considers strawberry ice cream his favorite dessert.",
        "timestamp": 50.0,
    }
    result = service.verify_claim(claim)
    assert result.verdict == VerdictType.UNVERIFIABLE
    assert "No verifiable evidence found" in result.reason


def test_verdict_unverifiable_conflicting_evidence():
    """Tests conflicting evidence reports leading to Unverifiable verdict."""
    service = VerificationService()
    claim = {
        "type": "claim",
        "claimId": "claim_conflict_01",
        "speaker": "Speaker 2",
        "claim": "The new product release will occur exactly on November 15.",
        "timestamp": 60.0,
    }
    result = service.verify_claim(claim)
    assert result.verdict == VerdictType.UNVERIFIABLE
    assert "conflicting" in result.reason.lower() or "inconclusive" in result.reason.lower()


# ---------------------------------------------------------------------------
# 5. Checker Edge Cases (Direct Checker Tests)
# ---------------------------------------------------------------------------

def test_checker_weak_evidence():
    """Ensures evidence with confidence below threshold yields Unverifiable."""
    checker = VerificationChecker(min_confidence_threshold=0.8)
    weak_evidence = [
        EvidenceItem(
            snippet="Some unverified rumor on a blog.",
            source_url="https://unverifiedblog.example.com",
            stance="supports",
            confidence=0.3,
        )
    ]
    verdict, reason, source = checker.verify("Unverified assertion", weak_evidence)
    assert verdict == VerdictType.UNVERIFIABLE
    assert "sufficient confidence" in reason


def test_checker_opposing_stances():
    """Ensures mixed support and refutation stances yield Unverifiable."""
    checker = VerificationChecker()
    opposing_evidence = [
        EvidenceItem(
            snippet="Source A confirms the claim.",
            source_url="https://source-a.com",
            stance="supports",
            confidence=0.9,
        ),
        EvidenceItem(
            snippet="Source B refutes the claim.",
            source_url="https://source-b.com",
            stance="refutes",
            confidence=0.9,
        ),
    ]
    verdict, reason, source = checker.verify("Disputed assertion", opposing_evidence)
    assert verdict == VerdictType.UNVERIFIABLE
    assert "conflicting" in reason.lower()


# ---------------------------------------------------------------------------
# 6. Service Batch & Mock Dataset Tests
# ---------------------------------------------------------------------------

def test_batch_verification():
    """Tests batch verification processing multiple claims."""
    service = VerificationService()
    results = service.verify_batch(MOCK_CLAIMS)
    assert len(results) == len(MOCK_CLAIMS)
    for original, verified in zip(MOCK_CLAIMS, results):
        assert verified.claimId == original["claimId"]
        assert verified.verdict in (VerdictType.TRUE, VerdictType.FALSE, VerdictType.UNVERIFIABLE)
        assert verified.reason != ""
        assert verified.source != ""


def test_all_verdict_types_represented_in_mock_claims():
    """Ensures mock dataset exercises all three required verdict types."""
    service = VerificationService()
    results = service.verify_batch(MOCK_CLAIMS)
    verdicts = {r.verdict for r in results}
    assert VerdictType.TRUE in verdicts
    assert VerdictType.FALSE in verdicts
    assert VerdictType.UNVERIFIABLE in verdicts
