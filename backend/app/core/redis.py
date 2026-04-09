from app.core.config import settings

try:  # pragma: no cover - optional dependency handling
    import redis
except ImportError:  # pragma: no cover
    redis = None


_redis_client = None


def get_redis_client():
    global _redis_client
    if not settings.REDIS_AVAILABLE or redis is None:
        return None
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=settings.HEALTHCHECK_TIMEOUT_SECONDS,
            socket_timeout=settings.HEALTHCHECK_TIMEOUT_SECONDS,
        )
    return _redis_client


def ping_redis() -> tuple[bool, str]:
    if not settings.REDIS_AVAILABLE:
        return True, "disabled"
    if redis is None:
        return False, "redis_package_not_installed"

    try:
        client = get_redis_client()
        assert client is not None
        client.ping()
        return True, "ok"
    except Exception as exc:  # pragma: no cover - defensive health path
        return False, str(exc)


def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        finally:
            _redis_client = None
