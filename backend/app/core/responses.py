from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.core.request_context import get_request_id, get_trace_id

T = TypeVar("T")


class ResponseMeta(BaseModel):
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    version: str = settings.APP_VERSION


class ResponseError(BaseModel):
    key: str


class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None
    error: ResponseError | None = None
    meta: ResponseMeta | None = None


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


def _meta_payload() -> dict:
    return {
        "request_id": get_request_id(),
        "trace_id": get_trace_id(),
        "version": settings.APP_VERSION,
    }


def _build_response(code: int, message: str, data: Any = None) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data,
        "meta": _meta_payload(),
    }


def ok(data: Any = None, message: str = "success") -> dict:
    return _build_response(200, message, data)


def created(data: Any = None, message: str = "created") -> dict:
    return _build_response(201, message, data)


def error(code: int, message: str, data: Any = None) -> dict:
    return _build_response(code, message, data)


def paginated(items: list, total: int, page: int, page_size: int) -> dict:
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    return _build_response(
        200,
        "success",
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    )
