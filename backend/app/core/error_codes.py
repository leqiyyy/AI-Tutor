from enum import IntEnum, StrEnum


class ErrorCode(IntEnum):
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    VALIDATION_ERROR = 422
    INTERNAL_ERROR = 500
    UPSTREAM_UNAVAILABLE = 503


class ErrorKey(StrEnum):
    BAD_REQUEST = "bad_request"
    AUTH_REQUIRED = "auth_required"
    FORBIDDEN = "forbidden"
    RESOURCE_NOT_FOUND = "resource_not_found"
    RESOURCE_CONFLICT = "resource_conflict"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"


STATUS_TO_ERROR_KEY: dict[int, ErrorKey] = {
    ErrorCode.BAD_REQUEST.value: ErrorKey.BAD_REQUEST,
    ErrorCode.UNAUTHORIZED.value: ErrorKey.AUTH_REQUIRED,
    ErrorCode.FORBIDDEN.value: ErrorKey.FORBIDDEN,
    ErrorCode.NOT_FOUND.value: ErrorKey.RESOURCE_NOT_FOUND,
    ErrorCode.CONFLICT.value: ErrorKey.RESOURCE_CONFLICT,
    ErrorCode.VALIDATION_ERROR.value: ErrorKey.VALIDATION_ERROR,
    ErrorCode.INTERNAL_ERROR.value: ErrorKey.INTERNAL_ERROR,
    ErrorCode.UPSTREAM_UNAVAILABLE.value: ErrorKey.UPSTREAM_UNAVAILABLE,
}


def error_key_for_status(status_code: int) -> ErrorKey:
    return STATUS_TO_ERROR_KEY.get(status_code, ErrorKey.INTERNAL_ERROR)
