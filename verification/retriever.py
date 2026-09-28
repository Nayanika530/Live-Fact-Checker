"""Evidence retriever module.

Defines the abstract EvidenceRetriever interface and provides a zero-dependency
MockRetriever for local development and testing, along with an extensible stub for
connecting real web search engines (Tavily, Serper, Bing, etc.) in the future.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import re

from verification.models import EvidenceItem


class EvidenceRetriever(ABC):
    """Abstract interface for evidence retrieval components."""

    @abstractmethod
    def retrieve(self, query: str, max_results: int = 3) -> List[EvidenceItem]:
        """Retrieves relevant evidence snippets and sources for a given query.

        Args:
            query: The generated search query.
            max_results: Maximum number of evidence snippets to return.

        Returns:
            A list of EvidenceItem objects.
        """
        pass


class MockRetriever(EvidenceRetriever):
    """Local, deterministic evidence retriever for testing and offline development.

    Uses keyword/token overlap against an internal knowledge base to simulate
    retrieval from authoritative publications without external network or API calls.
    """

    def __init__(self, custom_records: Optional[Dict[str, List[EvidenceItem]]] = None):
        """Initializes mock retriever with default knowledge base and optional custom records."""
        self._records: List[dict] = []
        self._seed_default_knowledge_base()

        if custom_records:
            for keyword, items in custom_records.items():
                self.register_evidence(keywords=[keyword], items=items)

    def _seed_default_knowledge_base(self) -> None:
        """Seeds standard test knowledge items covering true, false, conflicting, and statistical claims."""
        # 1. Company units sold (Numerical mismatch -> False)
        self.register_evidence(
            keywords=["company", "sold", "two million", "units", "million units"],
            items=[
                EvidenceItem(
                    snippet="Official regulatory filings confirm the company sold 1.2 million units in fiscal year 2023.",
                    source_url="https://sec.gov/edgar/filings/company-annual-2023.pdf",
                    title="SEC Annual Disclosure Report 2023",
                    stance="refutes",
                    confidence=0.98,
                )
            ],
        )

        # 2. Apollo 11 Moon landing (Clearly True)
        self.register_evidence(
            keywords=["apollo", "moon", "1969", "neil armstrong", "astronauts"],
            items=[
                EvidenceItem(
                    snippet="NASA's Apollo 11 successfully landed humans on the Moon on July 20, 1969.",
                    source_url="https://www.nasa.gov/mission_pages/apollo/apollo-11.html",
                    title="NASA Apollo 11 Mission Overview",
                    stance="supports",
                    confidence=0.99,
                )
            ],
        )

        # 3. Mount Everest location (Clearly False)
        self.register_evidence(
            keywords=["mount everest", "everest", "africa", "highest peak", "peak in africa"],
            items=[
                EvidenceItem(
                    snippet="Mount Everest is located in the Himalayas on the border of Nepal and China in Asia. Mount Kilimanjaro is the highest peak in Africa.",
                    source_url="https://britannica.com/place/Mount-Everest",
                    title="Encyclopaedia Britannica - Mount Everest",
                    stance="refutes",
                    confidence=0.99,
                )
            ],
        )

        # 4. Product release date (Conflicting evidence -> Unverifiable)
        self.register_evidence(
            keywords=["product release", "november 15", "release date", "launch date"],
            items=[
                EvidenceItem(
                    snippet="Tech Insider reports internal memos scheduling the product release for November 15.",
                    source_url="https://techinsider.example.com/exclusive-launch-dates",
                    title="Tech Insider Report",
                    stance="conflicting",
                    confidence=0.70,
                ),
                EvidenceItem(
                    snippet="Supply chain analysts state production bottlenecks delayed the product launch to Q1 next year.",
                    source_url="https://supplychaindaily.example.com/delays-confirmed",
                    title="Supply Chain Daily",
                    stance="conflicting",
                    confidence=0.72,
                ),
            ],
        )

        # 5. Inflation rate claim (Numerical exaggeration -> False)
        self.register_evidence(
            keywords=["inflation", "dropped", "15%", "15 percent", "rate dropped"],
            items=[
                EvidenceItem(
                    snippet="The Bureau of Labor Statistics reported consumer inflation slowed by 0.5% year-over-year, not 15%.",
                    source_url="https://bls.gov/cpi/latest-numbers.htm",
                    title="Bureau of Labor Statistics Consumer Price Index",
                    stance="refutes",
                    confidence=0.95,
                )
            ],
        )

        # 6. Earth orbits the Sun (Clearly True)
        self.register_evidence(
            keywords=["earth", "orbits", "sun", "solar system"],
            items=[
                EvidenceItem(
                    snippet="Earth completes one revolution around the Sun approximately every 365.25 days.",
                    source_url="https://solarsystem.nasa.gov/planets/earth/in-depth/",
                    title="NASA Solar System Exploration - Earth",
                    stance="supports",
                    confidence=1.0,
                )
            ],
        )

    def register_evidence(self, keywords: List[str], items: List[EvidenceItem]) -> None:
        """Dynamically registers evidence for matching queries during tests."""
        self._records.append({
            "keywords": [kw.lower() for kw in keywords],
            "items": items,
        })

    def retrieve(self, query: str, max_results: int = 3) -> List[EvidenceItem]:
        """Searches internal mock records for best token/keyword overlap."""
        if not query or not query.strip():
            return []

        normalized_query = query.lower()
        query_tokens = set(re.findall(r"\w+", normalized_query))

        best_matches: List[EvidenceItem] = []
        best_score = 0

        for record in self._records:
            match_score = 0
            for kw in record["keywords"]:
                # Check for exact substring match
                if kw in normalized_query:
                    match_score += 3
                else:
                    # Check token overlap
                    kw_tokens = set(re.findall(r"\w+", kw))
                    overlap = len(query_tokens.intersection(kw_tokens))
                    match_score += overlap

            if match_score > best_score and match_score >= 2:
                best_score = match_score
                best_matches = record["items"]

        return best_matches[:max_results]


class WebSearchRetriever(EvidenceRetriever):
    """Stub for plugging in real web search APIs (e.g. Tavily, Serper, Bing).

    Designed to drop into the pipeline without altering verification logic.
    """

    def __init__(self, api_key: Optional[str] = None, provider: str = "tavily"):
        self.api_key = api_key
        self.provider = provider

    def retrieve(self, query: str, max_results: int = 3) -> List[EvidenceItem]:
        """Placeholder for web API retrieval.
        
        Raises RuntimeError if attempted without configured API key.
        """
        if not self.api_key:
            raise RuntimeError(
                f"WebSearchRetriever ({self.provider}) requires an API key. "
                "Use MockRetriever for offline development and testing."
            )
        # Future implementation: HTTP call to Tavily/Serper API
        return []
