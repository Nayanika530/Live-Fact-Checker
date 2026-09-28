"""Claim engine adapter boundary.

The backend never runs a claim-extraction model. It defines the interface
Atif's claim intelligence must satisfy and hands it a validated
:class:`~backend.schemas.TranscriptEvent`.

Contract for an implementation:

* return zero or more backend :class:`~backend.schemas.ClaimEvent` objects
* copy ``sessionId``, ``speaker`` and ``timestamp`` from the transcript so the
  frontend can place the claim card on the right line
* mint a stable, unique ``claimId``; the same value must reach the
  verification event so the frontend can correlate them
* raise :class:`ClaimEngineError` on failure so the backend can emit a
  structured ``error`` event instead of crashing
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from backend.schemas import ClaimEvent, TranscriptEvent


class ClaimEngineError(RuntimeError):
    """Raised when claim extraction fails."""


class ClaimEngine(ABC):
    """Interface between the backend and the claim intelligence module."""

    name: str = "claim-engine"

    @abstractmethod
    async def extract_claims(
        self, transcript: TranscriptEvent
    ) -> List[ClaimEvent]:
        """Return the checkable claims contained in one transcript event.

        Args:
            transcript: A validated final transcript segment.

        Returns:
            Claims in speaking order. An empty list means the segment held no
            checkable claim (greetings, filler, opinion).
        """
        raise NotImplementedError


class UnavailableClaimEngine(ClaimEngine):
    """Placeholder used when no claim engine is wired in yet.

    Every call fails cleanly, so the backend emits a structured
    ``CLAIM_EXTRACTION_FAILED`` error event instead of pretending a claim was
    detected. This is the default whenever ``USE_MOCK_ENGINES=false`` and
    Atif's module has not been integrated.
    """

    name = "unavailable-claim-engine"

    async def extract_claims(
        self, transcript: TranscriptEvent
    ) -> List[ClaimEvent]:
        raise ClaimEngineError(
            "No claim engine is configured. Set USE_MOCK_ENGINES=true for the "
            "mock pipeline, or integrate Atif's claim intelligence module."
        )


class StaticClaimEngine(ClaimEngine):
    """Test double that maps transcripts to preconfigured claims.

    Useful for backend-only tests and for replaying a fixed scenario without
    any model call.
    """

    name = "static-claim-engine"

    def __init__(self, claims: Optional[Sequence[ClaimEvent]] = None) -> None:
        self._claims = list(claims or [])

    async def extract_claims(
        self, transcript: TranscriptEvent
    ) -> List[ClaimEvent]:
        return [
            claim.model_copy(
                update={
                    "sessionId": transcript.sessionId,
                    "speaker": transcript.speaker or claim.speaker,
                    "timestamp": transcript.timestamp,
                }
            )
            for claim in self._claims
        ]
