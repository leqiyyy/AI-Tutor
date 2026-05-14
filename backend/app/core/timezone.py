from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings


@lru_cache(maxsize=1)
def app_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.APP_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_app_timezone(value: datetime) -> datetime:
    return ensure_aware_utc(value).astimezone(app_timezone())


def isoformat_app_timezone(value: datetime) -> str:
    return to_app_timezone(value).isoformat()


def date_app_timezone(value: datetime) -> str:
    return to_app_timezone(value).date().isoformat()
