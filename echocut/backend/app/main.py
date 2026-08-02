import logging
import uuid

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router
from .config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(message)s")
logger = structlog.get_logger()
app = FastAPI(
    title="EchoCut API",
    version="0.1.0",
    description="Phase 1 operational API for EchoCut — The AI Test Audience",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:80]
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request.complete",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    code = {401: "unauthorized", 404: "not_found", 409: "conflict"}.get(
        exc.status_code, "request_error"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": first.get("msg", "Invalid request"),
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.get("/health", tags=["health"], summary="Process liveness")
async def health():
    return {"status": "ready", "service": "echocut-api"}


app.include_router(router)
