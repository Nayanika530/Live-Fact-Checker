"""Service health endpoint."""

from fastapi import APIRouter, Request

from backend.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Report service health plus non-sensitive wiring information.

    Only *whether* a credential is configured is reported, never its value.
    """
    settings = request.app.state.settings
    session_manager = request.app.state.session_manager
    websocket_manager = request.app.state.websocket_manager
    claim_engine = request.app.state.claim_engine
    verification_engine = request.app.state.verification_engine

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        sessions=await session_manager.count(),
        websocketClients=websocket_manager.connection_count(),
        engines={
            "claimEngine": getattr(claim_engine, "name", type(claim_engine).__name__),
            "verificationEngine": getattr(
                verification_engine, "name", type(verification_engine).__name__
            ),
        },
        credentialsConfigured={
            "assemblyai": settings.has_assemblyai_key(),
            "llmGateway": settings.has_llm_gateway_key(),
            "search": settings.has_search_key(),
        },
    )
