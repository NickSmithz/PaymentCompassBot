import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings


logger = logging.getLogger(__name__)
DEFAULT_PLANNING_HORIZON_DAYS = 90


def _override_date(settings) -> date | None:
    override = (settings.current_date_override or "").strip()
    if settings.dev_mode and override:
        try:
            return date.fromisoformat(override)
        except ValueError:
            logger.warning("Invalid CURRENT_DATE_OVERRIDE=%s; using real local date", override)
    return None


def get_now() -> datetime:
    settings = get_settings()
    now = datetime.now(ZoneInfo(settings.timezone))
    override = _override_date(settings)
    if override is not None:
        return now.replace(year=override.year, month=override.month, day=override.day)
    return now


def get_today() -> date:
    settings = get_settings()
    override = _override_date(settings)
    if override is not None:
        return override
    return datetime.now(ZoneInfo(settings.timezone)).date()


def get_planning_horizon_days(user_id: int | None = None) -> int:
    del user_id
    return get_settings().planning_horizon_days or DEFAULT_PLANNING_HORIZON_DAYS


def get_planning_horizon_end(user_id: int | None, base_date: date) -> date:
    return base_date + timedelta(days=get_planning_horizon_days(user_id))
