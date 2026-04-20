from contextvars import ContextVar, Token

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_request_id(request_id: str) -> Token:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token) -> None:
    _request_id_ctx.reset(token)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def set_trace_id(trace_id: str) -> Token:
    return _trace_id_ctx.set(trace_id)


def reset_trace_id(token: Token) -> None:
    _trace_id_ctx.reset(token)


def get_trace_id() -> str | None:
    return _trace_id_ctx.get()
