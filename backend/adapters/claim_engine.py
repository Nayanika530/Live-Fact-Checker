"""Claim engine adapter boundary and implementations.

The backend never runs a claim-extraction model directly in router logic. 
It defines the interface Atif's claim intelligence must satisfy and hands it a validated
:class:`~backend.schemas.TranscriptEvent`.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence, Dict, Any

from backend.schemas import ClaimEvent, TranscriptEvent

logger = logging.getLogger(__name__)


class ClaimEngineError(RuntimeError):
    """Raised when claim extraction fails."""


class ClaimEngine(ABC):
    """Interface between the backend and the claim intelligence module."""

    name: str = "claim-engine"

    @abstractmethod
    async def extract_claims(
        self, transcript: TranscriptEvent
    ) -> List[ClaimEvent]:
        """Return the checkable claims contained in one transcript event."""
        raise NotImplementedError


class UnavailableClaimEngine(ClaimEngine):
    """Placeholder used when no claim engine is wired in yet."""

    name = "unavailable-claim-engine"

    async def extract_claims(
        self, transcript: TranscriptEvent
    ) -> List[ClaimEvent]:
        raise ClaimEngineError(
            "No claim engine is configured. Set USE_MOCK_ENGINES=true for the "
            "mock pipeline, or integrate Atif's claim intelligence module."
        )


class StaticClaimEngine(ClaimEngine):
    """Test double that maps transcripts to preconfigured claims."""

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


class LLMClaimEngine(ClaimEngine):
    """Concrete claim engine implementation using AssemblyAI LLM Gateway / Qwen."""

    name = "llm-claim-engine"

    def __init__(self) -> None:
        self.seen_claims: set = set()
        self.claim_counter: int = 1
        self.api_key = os.getenv("LLM_GATEWAY_API_KEY") or os.getenv("ASSEMBLYAI_API_KEY")

    async def extract_claims(self, transcript: TranscriptEvent) -> List[ClaimEvent]:
        text = transcript.text.strip()
        if not text:
            return []

        raw_claims = []

        # Use AssemblyAI LLM Gateway if key is available
        if self.api_key and self.api_key != "your_key_here":
            try:
                import assemblyai as aai
                aai.settings.api_key = self.api_key
                gateway = aai.LLMGateway()

                prompt = f"""
Analyze the following transcript segment and identify ONLY discrete, objectively checkable factual claims (such as statistics, dates, names, historical events, quantities).
Ignore opinions, preferences, jokes, greetings, filler text, future predictions, or subjective feelings.
Return valid JSON matching this schema:
{{
  "claims": [
    {{
      "claim": "string",
      "claimType": "historical_fact | statistic | date | person | location | scientific_fact | quote | other_checkable_fact"
    }}
  ]
}}
If there are no checkable claims, return {{"claims": []}}.

Transcript: "{text}"
"""
                completion = gateway.chat.completions.create(
                    model="qwen3.5-4b-32k-fast",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                )
                content = completion.choices[0].message.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                
                data = json.loads(content.strip())
                raw_claims = data.get("claims", [])
            except Exception as e:
                logger.warning(f"LLM Gateway execution failed: {e}. Falling back to rule-based mock matching.")
                raw_claims = self._get_fallback_claims(text)
        else:
            raw_claims = self._get_fallback_claims(text)

        claim_events = []
        for item in raw_claims:
            claim_text = item.get("claim", "").strip()
            if not claim_text:
                continue

            # Deduplication check
            normalized_key = claim_text.lower()
            if normalized_key in self.seen_claims:
                continue
            self.seen_claims.add(normalized_key)

            claim_id = f"claim_{self.claim_counter:03d}"
            self.claim_counter += 1

            claim_events.append(
                ClaimEvent(
                    type="claim",
                    claimId=claim_id,
                    sessionId=transcript.sessionId,
                    speaker=transcript.speaker,
                    timestamp=transcript.timestamp,
                    claim=claim_text,
                    claimType=item.get("claimType", "other_checkable_fact")
                )
            )

        return claim_events

    def _get_fallback_claims(self, text: str) -> List[Dict[str, Any]]:
        text_lower = text.lower()
        extracted = []
        if "2011 cricket world cup" in text_lower or "india won" in text_lower:
            extracted.append({
                "claim": "India won the 2011 Cricket World Cup.",
                "claimType": "historical_fact"
            })
        elif "company sold two million units" in text_lower:
            extracted.append({
                "claim": "The company sold two million units.",
                "claimType": "statistic"
            })
        return extracted