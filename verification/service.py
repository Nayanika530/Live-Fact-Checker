"""Main verification service orchestrating the verification pipeline.

Pipeline stages:
ClaimEvent
→ query generation
→ evidence retrieval
→ verification
→ VerificationEvent (with original claimId strictly preserved)
"""

import sys
from pathlib import Path
from typing import List, Optional, Union

# Ensure project root is in sys.path when executed directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from verification.checker import VerificationChecker
from verification.models import ClaimEvent, VerificationEvent
from verification.query_generator import generate_search_query
from verification.retriever import EvidenceRetriever, MockRetriever


class VerificationService:
    """Service handling the end-to-end fact verification workflow."""

    def __init__(
        self,
        retriever: Optional[EvidenceRetriever] = None,
        checker: Optional[VerificationChecker] = None,
    ):
        """Initializes the verification service with configurable retriever and checker.

        Args:
            retriever: EvidenceRetriever implementation (defaults to MockRetriever).
            checker: VerificationChecker implementation (defaults to standard checker).
        """
        self.retriever = retriever if retriever is not None else MockRetriever()
        self.checker = checker if checker is not None else VerificationChecker()

    def verify_claim(self, claim_input: Union[ClaimEvent, dict]) -> VerificationEvent:
        """Runs a single ClaimEvent through the verification pipeline.

        Args:
            claim_input: A ClaimEvent instance or a raw dictionary adhering to the contract.

        Returns:
            A VerificationEvent with preserved claimId and determined verdict.
        """
        # 1. Parse & validate input contract
        if isinstance(claim_input, dict):
            claim_event = ClaimEvent(**claim_input)
        elif isinstance(claim_input, ClaimEvent):
            claim_event = claim_input
        else:
            raise TypeError(f"Expected ClaimEvent or dict, received {type(claim_input)}")

        # 2. Query generation
        query = generate_search_query(claim_event.claim)

        # 3. Evidence retrieval
        evidence = self.retriever.retrieve(query)

        # 4. Comparison and verification
        verdict, reason, source = self.checker.verify(claim_event.claim, evidence)

        # 5. Output contract with strictly preserved claimId
        return VerificationEvent(
            type="verification",
            claimId=claim_event.claimId,
            verdict=verdict,
            reason=reason,
            source=source,
        )

    def verify_batch(self, claims: List[Union[ClaimEvent, dict]]) -> List[VerificationEvent]:
        """Runs a sequence of claims through the verification pipeline."""
        return [self.verify_claim(c) for c in claims]


def verify_claim_event(
    claim_input: Union[ClaimEvent, dict],
    retriever: Optional[EvidenceRetriever] = None,
) -> VerificationEvent:
    """Convenience functional interface for verifying a single claim."""
    service = VerificationService(retriever=retriever)
    return service.verify_claim(claim_input)
