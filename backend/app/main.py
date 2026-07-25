from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings

logger = logging.getLogger("kondai.api")
settings = get_settings()

# Build the actual FastAPI application first.
# It is wrapped by CORSMiddleware at the bottom of this file so that even
# unhandled 500 responses contain CORS headers. This prevents real backend
# exceptions from being hidden by the browser as misleading CORS errors.
api = FastAPI(
    title=settings.app_name,
    version="1.0.1",
    description="Kondai Founder Operations Platform",
)


@api.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled API error for %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "The backend encountered an unexpected error.",
            "path": request.url.path,
        },
    )


api.include_router(router, prefix=settings.api_prefix)


@api.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": settings.app_name,
        "version": "1.0.1",
        "environment": settings.environment,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
        "frontend_url": settings.frontend_url,
        "public_api_base_url": settings.public_api_base_url,
        "allowed_origins": settings.allowed_origins,
    }


@api.get(f"{settings.api_prefix}/cors-status", include_in_schema=False)
async def cors_status(request: Request) -> dict[str, Any]:
    """Small deployment diagnostic endpoint; it exposes no secrets."""
    return {
        "status": "ok",
        "request_origin": request.headers.get("origin"),
        "allowed_origins": settings.allowed_origins,
        "environment": settings.environment,
    }


# IMPORTANT: wrap the entire FastAPI application instead of only calling
# api.add_middleware(...). Global wrapping ensures CORS headers are also added
# to error responses generated outside FastAPI's normal exception stack.
app = CORSMiddleware(
    app=api,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
        "Origin",
        "X-Requested-With",
        "X-User-Id",
        "X-Workspace-Id",
    ],
    expose_headers=["Content-Disposition"],
    max_age=86400,
)
