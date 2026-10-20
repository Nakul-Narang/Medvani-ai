"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.graph import build_pipeline
from app.agents.nodes import Services
from app.api.v1 import consult, health
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.security import SlidingWindowRateLimiter
from app.services.retriever import GuidelineRetriever
from app.services.safety import SafetyService
from app.services.translator import build_translator

logger = logging.getLogger("medvani")


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc = services or Services(
            settings=settings,
            translator=build_translator(settings),
            retriever=GuidelineRetriever.from_file(settings.guidelines_path),
            safety=SafetyService(),
        )
        app.state.services = svc
        app.state.pipeline = build_pipeline(svc)
        logger.info(
            "startup complete",
            extra={
                "engine": app.state.pipeline.engine,
                "guidelines": len(svc.retriever),
                "translator": settings.translator_provider,
                "env": settings.environment,
            },
        )
        yield

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description="Multilingual medical-information RAG pipeline with deterministic safety rules.",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()

        if request.url.path.startswith("/api/"):
            client = _client_ip(request, settings.trust_proxy_headers)
            allowed, retry_after = request.app.state.limiter.allow(client)
            if not allowed:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down.", "request_id": request_id},
                    headers={"Retry-After": str(retry_after)},
                )
                response.headers["X-Request-ID"] = request_id
                return response

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # Do not echo the submitted body back (it may contain health details).
        errors = [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors, "request_id": request.state.request_id})

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal error. If this is an emergency, call 112.",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    app.include_router(health.router)
    app.include_router(consult.router, prefix="/api/v1")
    return app


def _client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


app = create_app()
