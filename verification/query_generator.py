"""Search query generator for fact-checking claims.

Transforms raw, conversational claim statements into concise, focused search
queries suitable for evidence retrieval engines.
"""

import re

# Conversational prefixes and discourse markers frequently found in live speech
CONVERSATIONAL_PREFIXES = [
    r"^i\s+(think|believe|feel|guess|heard|suppose)\s+(that\s+)?",
    r"^(in\s+my\s+opinion|to\s+be\s+honest|as\s+we\s+know|as\s+you\s+know|frankly|actually|basically|essentially),?\s*",
    r"^(speaker\s+\d+|the\s+speaker|they|he|she)\s+(said|stated|claimed|mentioned|noted)\s+(that\s+)?",
    r"^(it\s+is\s+well\s+known\s+that|everybody\s+knows\s+that|the\s+truth\s+is\s+that)\s*",
    r"^(look|well|listen|you\s+see),?\s*",
]

# Filler words and hedges to strip out
FILLER_PATTERNS = [
    r"\b(like|literally|totally|basically|obviously|allegedly|reportedly)\b",
]


def clean_conversational_text(text: str) -> str:
    """Removes speech artifacts, discourse markers, and conversational hedges."""
    cleaned = text.strip()

    # Iteratively strip conversational prefixes until no more match
    changed = True
    while changed:
        changed = False
        for pattern in CONVERSATIONAL_PREFIXES:
            new_cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
            if new_cleaned != cleaned:
                cleaned = new_cleaned
                changed = True

    # Strip filler words
    for pattern in FILLER_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Collapse multiple spaces and remove outer quotes
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^[\"']|[\"']$", "", cleaned).strip()
    return cleaned


def generate_search_query(claim_text: str, max_words: int = 12) -> str:
    """Converts a claim statement into a concise, focused search query.

    Args:
        claim_text: The raw claim sentence extracted from transcript.
        max_words: Maximum number of search terms in the resulting query.

    Returns:
        A concise search query string.

    Examples:
        "The company sold two million units."
        -> "company sold two million units"

        "Speaker 1 said that Mount Everest is located in Africa."
        -> "Mount Everest located in Africa"
    """
    if not claim_text or not claim_text.strip():
        return ""

    cleaned = clean_conversational_text(claim_text)

    # Remove ending punctuation (. ! ?) but keep internal periods in numbers (e.g. 2.5)
    cleaned = re.sub(r"[?!;:,]+$", "", cleaned)
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]

    # Normalize whitespace
    words = cleaned.split()
    if len(words) > max_words:
        # Keep the most relevant leading assertion words
        cleaned = " ".join(words[:max_words])

    return cleaned.strip()
