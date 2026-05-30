from datetime import date

import pytest

from app.config import get_settings
from app.services.planning import get_planning_horizon_end, get_today


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_current_date_override_sets_horizon_end_may_30(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-05-30")
    monkeypatch.setenv("PLANNING_HORIZON_DAYS", "90")

    today = get_today()

    assert today == date(2026, 5, 30)
    assert get_planning_horizon_end(user_id=None, base_date=today) == date(2026, 8, 28)


def test_current_date_override_sets_horizon_end_june_10(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-06-10")
    monkeypatch.setenv("PLANNING_HORIZON_DAYS", "90")

    today = get_today()

    assert today == date(2026, 6, 10)
    assert get_planning_horizon_end(user_id=None, base_date=today) == date(2026, 9, 8)


def test_current_date_override_sets_horizon_end_june_20(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-06-20")
    monkeypatch.setenv("PLANNING_HORIZON_DAYS", "90")

    today = get_today()

    assert today == date(2026, 6, 20)
    assert get_planning_horizon_end(user_id=None, base_date=today) == date(2026, 9, 18)


def test_current_date_override_is_ignored_when_dev_mode_is_false(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "1999-01-01")

    assert get_today() != date(1999, 1, 1)
