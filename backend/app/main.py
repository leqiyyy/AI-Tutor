from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
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
from app.core.redis import close_redis
from app.core.responses import ok

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
    yield
    close_redis()
    logger.info("app_stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Tutor backend service",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
    started = perf_counter()
    request.state.request_id = request_id
    response = await call_next(request)
    duration_ms = round((perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http_request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


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
def health():
    snapshot = get_system_health_payload()
    return ok(data=snapshot, message=snapshot["status"])


@app.get("/health/live", tags=["system"])
def health_live():
    return ok(data=get_liveness_payload())


@app.get("/health/ready", tags=["system"])
def health_ready():
    snapshot = get_readiness_payload()
    return ok(data=snapshot, message=snapshot["status"])
