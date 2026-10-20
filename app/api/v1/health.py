from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness: the process is up. Used by the platform health check."""
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request):
    """Readiness: the knowledge base and pipeline are loaded."""
    pipeline = getattr(request.app.state, "pipeline", None)
    services = getattr(request.app.state, "services", None)
    if pipeline is None or services is None:
        return JSONResponse(status_code=503, content={"status": "starting"})
    return {
        "status": "ready",
        "version": request.app.state.settings.version,
        "engine": pipeline.engine,
        "guidelines": len(services.retriever),
        "translator": request.app.state.settings.translator_provider,
    }
