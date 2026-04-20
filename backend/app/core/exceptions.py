from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.error_codes import ErrorCode, ErrorKey, error_key_for_status
from app.core.logging import get_logger
from app.core.request_context import get_request_id, get_trace_id

logger = get_logger(__name__)


def _response_content(
    code: int,
    message: str,
    data=None,
    error_key: ErrorKey | str | None = None,
) -> dict:
    payload = {
        "code": code,
        "message": message,
        "data": data,
        "meta": {
            "request_id": get_request_id(),
            "trace_id": get_trace_id(),
            "version": settings.APP_VERSION,
        },
    }
    if error_key is not None:
        key_value = error_key.value if isinstance(error_key, ErrorKey) else str(error_key)
        payload["error"] = {"key": key_value}
    return payload


class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        code: int,
        message: str,
        error_key: ErrorKey | str | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.error_key = error_key or error_key_for_status(status_code)


class AuthException(AppException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=ErrorCode.UNAUTHORIZED.value,
            code=ErrorCode.UNAUTHORIZED.value,
            message=message,
            error_key=ErrorKey.AUTH_REQUIRED,
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            status_code=ErrorCode.FORBIDDEN.value,
            code=ErrorCode.FORBIDDEN.value,
            message=message,
            error_key=ErrorKey.FORBIDDEN,
        )


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            status_code=ErrorCode.NOT_FOUND.value,
            code=ErrorCode.NOT_FOUND.value,
            message=message,
            error_key=ErrorKey.RESOURCE_NOT_FOUND,
        )


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request"):
        super().__init__(
            status_code=ErrorCode.BAD_REQUEST.value,
            code=ErrorCode.BAD_REQUEST.value,
            message=message,
            error_key=ErrorKey.BAD_REQUEST,
        )


class BusinessException(AppException):
    def __init__(
        self,
        message: str,
        code: int = ErrorCode.BAD_REQUEST.value,
        error_key: ErrorKey | str | None = None,
    ):
        super().__init__(ErrorCode.BAD_REQUEST.value, code, message, error_key=error_key or ErrorKey.BAD_REQUEST)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_response_content(
            code=exc.code,
            message=exc.message,
            data=None,
            error_key=exc.error_key,
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    status_code = exc.status_code
    return JSONResponse(
        status_code=status_code,
        content=_response_content(
            code=status_code,
            message=str(exc.detail),
            data=None,
            error_key=error_key_for_status(status_code),
        ),
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
        status_code=ErrorCode.VALIDATION_ERROR.value,
        content=_response_content(
            code=ErrorCode.VALIDATION_ERROR.value,
            message=message,
            data=None,
            error_key=ErrorKey.VALIDATION_ERROR,
        ),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=ErrorCode.INTERNAL_ERROR.value,
        content=_response_content(
            code=ErrorCode.INTERNAL_ERROR.value,
            message="Internal server error",
            data=None,
            error_key=ErrorKey.INTERNAL_ERROR,
        ),
    )
