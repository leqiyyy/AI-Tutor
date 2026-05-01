from contextlib import asynccontextmanager
import asyncio
import contextlib
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import initialize_database
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.health import (
    get_liveness_payload,
    get_readiness_payload,
    get_system_health_payload,
)
from app.core.logging import configure_logging, get_logger
from app.core.openapi_examples import DEFAULT_ERROR_RESPONSES
from app.core.request_context import reset_request_id, reset_trace_id, set_request_id, set_trace_id
from app.core.redis import close_redis
from app.core.responses import ok
from app.integrations.rag import shutdown_rag_engine
from app.services.rag_warmup_service import schedule_rag_warmup

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.DEBUG)
    logger.info(
        "app_starting",
        env=settings.ENV,
        version=settings.APP_VERSION,
        database_url=settings.DATABASE_URL,
        storage_backend=settings.STORAGE_BACKEND,
    )
    if settings.AUTO_CREATE_TABLES:
        initialize_database()
        logger.info("database_initialized", auto_create_tables=True)
    warmup_task = schedule_rag_warmup()
    yield
    if warmup_task and not warmup_task.done():
        warmup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warmup_task
    await shutdown_rag_engine()
    close_redis()
    logger.info("app_stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Tutor backend service",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    responses=DEFAULT_ERROR_RESPONSES,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = uuid4().hex
    incoming_trace_id = request.headers.get("X-Trace-ID")
    trace_id = incoming_trace_id.strip() if incoming_trace_id else request_id
    started = perf_counter()
    request.state.request_id = request_id
    request.state.trace_id = trace_id
    request_token = set_request_id(request_id)
    trace_token = set_trace_id(trace_id)
    try:
        response = await call_next(request)
        duration_ms = round((perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        logger.info(
            "http_request",
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response
    finally:
        reset_trace_id(trace_token)
        reset_request_id(request_token)


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["system"])
def root():
    return ok(
        data={
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }
    )


@app.get("/health", tags=["system"])
def health(response: Response):
    snapshot = get_system_health_payload()
    if not snapshot["ready"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ok(data=snapshot, message=snapshot["status"])


@app.get("/health/live", tags=["system"])
def health_live():
    return ok(data=get_liveness_payload())


@app.get("/health/ready", tags=["system"])
def health_ready(response: Response):
    snapshot = get_readiness_payload()
    if not snapshot["ready"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ok(data=snapshot, message=snapshot["status"])
