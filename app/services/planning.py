from datetime import date, timedelta

from app.config import get_settings


DEFAULT_PLANNING_HORIZON_DAYS = 90


def get_planning_horizon_days(user_id: int | None = None) -> int:
    del user_id
    return get_settings().planning_horizon_days or DEFAULT_PLANNING_HORIZON_DAYS


def get_planning_horizon_end(user_id: int | None, base_date: date) -> date:
    return base_date + timedelta(days=get_planning_horizon_days(user_id))
