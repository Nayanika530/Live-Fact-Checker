"""Live Fact-Checker backend package.

Owns the HTTP API, the WebSocket event layer, session management, event
validation, event routing, integration adapters, structured logging,
configuration, CORS and the mock pipeline.

The backend does not implement AssemblyAI streaming, claim extraction
algorithms, or search/evidence reasoning. It only routes validated events
between those modules and the frontend.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
