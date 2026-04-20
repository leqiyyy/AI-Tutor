from copy import deepcopy
from typing import Any

from app.core.config import settings
from app.core.error_codes import ErrorCode, ErrorKey

EXAMPLE_META = {
    "request_id": "2fe8eb4f540d49f59c18adcec0328572",
    "trace_id": "trace_demo_20260417",
    "version": settings.APP_VERSION,
}


def success_envelope(data: Any, message: str = "success", code: int = 200) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
        "meta": deepcopy(EXAMPLE_META),
    }


def error_envelope(
    status_code: int,
    message: str,
    error_key: ErrorKey,
) -> dict[str, Any]:
    return {
        "code": status_code,
        "message": message,
        "data": None,
        "error": {"key": error_key.value},
        "meta": deepcopy(EXAMPLE_META),
    }


DEFAULT_ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    ErrorCode.BAD_REQUEST.value: {
        "description": "Bad request",
        "content": {
            "application/json": {
                "example": error_envelope(
                    ErrorCode.BAD_REQUEST.value,
                    "Bad request",
                    ErrorKey.BAD_REQUEST,
                )
            }
        },
    },
    ErrorCode.UNAUTHORIZED.value: {
        "description": "Unauthorized",
        "content": {
            "application/json": {
                "example": error_envelope(
                    ErrorCode.UNAUTHORIZED.value,
                    "Authentication required",
                    ErrorKey.AUTH_REQUIRED,
                )
            }
        },
    },
    ErrorCode.FORBIDDEN.value: {
        "description": "Forbidden",
        "content": {
            "application/json": {
                "example": error_envelope(
                    ErrorCode.FORBIDDEN.value,
                    "Permission denied",
                    ErrorKey.FORBIDDEN,
                )
            }
        },
    },
    ErrorCode.NOT_FOUND.value: {
        "description": "Not found",
        "content": {
            "application/json": {
                "example": error_envelope(
                    ErrorCode.NOT_FOUND.value,
                    "Resource not found",
                    ErrorKey.RESOURCE_NOT_FOUND,
                )
            }
        },
    },
    ErrorCode.CONFLICT.value: {
        "description": "Conflict",
        "content": {
            "application/json": {
                "example": error_envelope(
                    ErrorCode.CONFLICT.value,
                    "Resource conflict",
                    ErrorKey.RESOURCE_CONFLICT,
                )
            }
        },
    },
    ErrorCode.VALIDATION_ERROR.value: {
        "description": "Validation error",
        "content": {
            "application/json": {
                "example": error_envelope(
                    ErrorCode.VALIDATION_ERROR.value,
                    "Validation failed",
                    ErrorKey.VALIDATION_ERROR,
                )
            }
        },
    },
    ErrorCode.INTERNAL_ERROR.value: {
        "description": "Internal server error",
        "content": {
            "application/json": {
                "example": error_envelope(
                    ErrorCode.INTERNAL_ERROR.value,
                    "Internal server error",
                    ErrorKey.INTERNAL_ERROR,
                )
            }
        },
    },
    ErrorCode.UPSTREAM_UNAVAILABLE.value: {
        "description": "Upstream dependency unavailable",
        "content": {
            "application/json": {
                "example": error_envelope(
                    ErrorCode.UPSTREAM_UNAVAILABLE.value,
                    "Upstream service unavailable",
                    ErrorKey.UPSTREAM_UNAVAILABLE,
                )
            }
        },
    },
}


def responses_with_success(
    example_data: Any,
    message: str = "success",
    status_code: int = 200,
    include_errors: tuple[int, ...] = (),
) -> dict[int, dict[str, Any]]:
    responses: dict[int, dict[str, Any]] = {
        status_code: {
            "description": "OK",
            "content": {
                "application/json": {
                    "example": success_envelope(
                        data=example_data,
                        message=message,
                        code=status_code,
                    )
                }
            },
        }
    }

    for code in include_errors:
        error_response = DEFAULT_ERROR_RESPONSES.get(code)
        if error_response:
            responses[code] = deepcopy(error_response)

    return responses
