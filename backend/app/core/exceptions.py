from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    def __init__(self, status_code: int, code: int, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


class AuthException(AppException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(401, 401, message)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(403, 403, message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(404, 404, message)


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request"):
        super().__init__(400, 400, message)


class BusinessException(AppException):
    def __init__(self, message: str, code: int = 400):
        super().__init__(400, code, message)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None},
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()
    message = "; ".join(
        f"{' -> '.join(str(loc) for loc in error['loc'])}: {error['msg']}"
        for error in errors
    )
    return JSONResponse(
        status_code=422,
        content={"code": 422, "message": message, "data": None},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "Internal server error", "data": None},
    )
