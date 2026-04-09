import json
import logging
import sys
from typing import Any

try:  # pragma: no cover - import fallback depends on local env
    import structlog
except ImportError:  # pragma: no cover - handled by fallback logger
    structlog = None


class FallbackLogger:
    """A tiny structured logger used when structlog is unavailable."""

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def bind(self, **_: Any) -> "FallbackLogger":
        return self

    def _emit(self, level: str, event: str, **kwargs: Any) -> None:
        message = event
        if kwargs:
            message = f"{event} {json.dumps(kwargs, default=str, sort_keys=True)}"
        getattr(self._logger, level)(message)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._emit("debug", event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit("info", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._emit("warning", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit("error", event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        self._emit("exception", event, **kwargs)


def configure_logging(debug: bool = False) -> None:
    """Configure application logging once at process startup."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if structlog is None:
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    if structlog is not None:
        return structlog.get_logger(name)
    return FallbackLogger(name)
