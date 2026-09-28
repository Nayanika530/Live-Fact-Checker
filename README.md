# Live Fact-Checker: Verification Module

This module implements the **Verification Subsystem** for the Live Fact-Checker project. It is responsible for taking extracted factual claims from live audio/speech transcripts, generating search queries, retrieving authoritative evidence, comparing statements against ground truth, and outputting structured verification results with source attribution and preserved claim tracking.

---

## Architecture & Pipeline Flow

The verification module executes a linear, decoupled pipeline:

```text
Claim Event
    │
    ▼
1. Query Generation (verification/query_generator.py)
   - Strips conversational speech prefixes, speaker tags, and filler words
   - Converts natural assertions into high-signal search queries
    │
    ▼
2. Evidence Retrieval (verification/retriever.py)
   - Retrieves authoritative evidence snippets via an abstract `EvidenceRetriever` interface
   - Ships with a zero-dependency `MockRetriever` for local offline testing
   - Pluggable `WebSearchRetriever` stub for future live search engines
    │
    ▼
3. Fact Checking & Stance Comparison (verification/checker.py)
   - Evaluates evidence stance, refutation markers, numerical figures, and consistency
   - Adheres to the principle: If evidence is missing, weak, or conflicting -> `Unverifiable`
   - Determines verdict (`True`, `False`, or `Unverifiable`)
   - Synthesizes concise reasoning and identifies primary source URL
    │
    ▼
4. Output Event Formulation (verification/service.py)
   - Returns a strictly validated `VerificationEvent`
   - Preserves original `claimId` throughout the entire pipeline
```

---

## Data Contracts

### 1. Input Contract: `ClaimEvent`

```json
{
  "type": "claim",
  "claimId": "claim_001",
  "speaker": "Speaker 1",
  "claim": "The company sold two million units.",
  "timestamp": 12.4
}
```

* **`type`**: Must be the literal string `"claim"`.
* **`claimId`**: Unique string identifier for the claim (must not be empty).
* **`speaker`**: Speaker identifier (e.g., `"Speaker 1"`).
* **`claim`**: Factual assertion extracted from speech.
* **`timestamp`**: Non-negative float representing the audio timestamp in seconds.

### 2. Output Contract: `VerificationEvent`

```json
{
  "type": "verification",
  "claimId": "claim_001",
  "verdict": "False",
  "reason": "The available source reports a different figure.",
  "source": "https://example.com"
}
```

* **`type`**: Must be the literal string `"verification"`.
* **`claimId`**: Preserved exact identifier from the corresponding `ClaimEvent`.
* **`verdict`**: Strict enumeration allowing only:
  * `"True"`
  * `"False"`
  * `"Unverifiable"`
* **`reason`**: Concise, human-readable rationale explaining the verdict.
* **`source`**: Authoritative URL or reference identifier.

---

## Directory Structure

```text
Live-Fact-Checker/
├── verification/
│   ├── __init__.py           # Package exports
│   ├── models.py             # Pydantic schemas (ClaimEvent, VerificationEvent, EvidenceItem)
│   ├── query_generator.py    # Speech artifact cleaning & query synthesis
│   ├── retriever.py          # EvidenceRetriever ABC, MockRetriever & WebSearchRetriever stub
│   ├── checker.py            # Comparison logic & 3-verdict determination
│   ├── service.py            # VerificationService orchestrator & CLI runner
│   └── mock_data.py          # Curated test datasets covering all edge cases
├── tests/
│   ├── __init__.py
│   └── test_verification.py  # Pytest test suite (contract, logic, edge cases)
├── .gitignore                # Git ignore rules (.venv, caches, env files)
├── requirements.txt          # Python dependencies (pydantic, pytest)
└── README.md                 # System documentation
```

---

## Installation & Setup

### Prerequisites
* Python 3.10+ (tested with Python 3.11)

### Setup Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate on Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Or activate on Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Running the Mock Verification Demo

To run the verification pipeline on sample mock claims covering all verdict types:

```bash
python verification/service.py
```

Or using module execution:

```bash
python -m verification.service
```

This will run through 6 distinct claim scenarios (clearly true, clearly false, numerical mismatch, unverifiable/no evidence, conflicting reports) and print the JSON `ClaimEvent` input and resulting `VerificationEvent` output for each.

---

## Running Automated Tests

Run the complete test suite with `pytest`:

```bash
pytest -v
```

### Test Coverage Highlights:
* **Contract Validation**: Verifies field constraints, non-empty validators, and rejection of malformed or extra fields.
* **Verdict Rules**: Asserts strict compliance with `"True"`, `"False"`, and `"Unverifiable"`.
* **`claimId` Preservation**: Ensures the ID passed into `verify_claim()` is identical in the returned `VerificationEvent`.
* **Query Cleaning**: Tests removal of speech filler (`"in my opinion"`, `"Speaker 1 said that"`).
* **Missing Evidence**: Guarantees unsupported/unseen claims return `"Unverifiable"` rather than guessing.
* **Conflicting Evidence**: Confirms that contradictory sources yield `"Unverifiable"`.
* **Numerical Fact Discrepancies**: Validates comparison between claimed figures and official figures.

---

## Integrating Real Search Providers

To connect a live search API (e.g. Tavily, Google Custom Search, Serper, Bing) during later integration stages:

1. Open `verification/retriever.py`.
2. Implement the `retrieve(query: str, max_results: int = 3) -> list[EvidenceItem]` method in `WebSearchRetriever` (or create a custom `TavilyRetriever(EvidenceRetriever)` subclass).
3. Inject your retriever into the `VerificationService`:

```python
from verification.service import VerificationService
from verification.retriever import WebSearchRetriever

# Initialize with your custom retriever instance
live_retriever = WebSearchRetriever(api_key="your_api_key", provider="tavily")
service = VerificationService(retriever=live_retriever)

# Run verification - the verification logic remains completely unchanged!
result = service.verify_claim(claim_event)
```

No modifications to `checker.py`, `models.py`, or `service.py` are needed when switching search backends.
