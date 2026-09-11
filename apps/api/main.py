"""
ShivAI FastAPI Main Application Entry Point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from monitoring.logging import configure_logging
from database.session import init_db
from apps.api.middleware.request_id import RequestIDMiddleware
from apps.api.middleware.security_headers import SecurityHeadersMiddleware
from apps.api.routers import (
    chat_router,
    conversations_router,
    memory_router,
    models_router,
    health_router,
)
from core.routing.fallback_handler import ShivAIServiceException


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title="ShivAI Core Backend",
    description="Resilient, Multi-Model Independent AI Engine powered by dynamic provider rotation and fallback.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 1. Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# 2. Request ID Tracking
app.add_middleware(RequestIDMiddleware)

# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(ShivAIServiceException)
async def handle_shivai_service_error(request: Request, exc: ShivAIServiceException):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=exc.to_dict(),
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", "req-unknown")
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        payload = exc.detail
        if "request_id" not in payload["error"]:
            payload["error"]["request_id"] = req_id
        return JSONResponse(status_code=exc.status_code, content=payload)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "request_id": req_id,
            }
        },
    )


@app.exception_handler(Exception)
async def handle_generic_exception(request: Request, exc: Exception):
    import logging
    req_id = getattr(request.state, "request_id", "req-unknown")
    logging.getLogger("shivai.api").exception(f"[{req_id}] Unhandled server exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"ShivAI server error: {str(exc)}",
                "request_id": req_id,
            }
        },
    )


# Include Routers
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(memory_router)
app.include_router(models_router)
app.include_router(health_router)
