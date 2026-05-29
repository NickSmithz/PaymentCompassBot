from datetime import date

from app.formatters import format_obligations_list
from app.texts import BTN_ADD_OBLIGATION


def test_empty_upcoming_without_obligations_shows_add_first_payment_message():
    text = format_obligations_list(
        {
            "items": [],
            "obligations_count": 0,
            "active_obligations_count": 0,
            "horizon_end": date(2026, 8, 27),
            "total_required": 0,
            "total_reserved": 0,
            "total_paid": 0,
            "total_remaining": 0,
        }
    )

    assert "Пока нет добавленных платежей" in text
    assert BTN_ADD_OBLIGATION in text


def test_empty_upcoming_with_existing_obligations_does_not_say_no_payments_added():
    text = format_obligations_list(
        {
            "items": [],
            "obligations_count": 1,
            "active_obligations_count": 1,
            "horizon_end": date(2026, 8, 27),
            "total_required": 0,
            "total_reserved": 0,
            "total_paid": 0,
            "total_remaining": 0,
        }
    )

    assert "Пока нет добавленных платежей" not in text
    assert "нет незакрытых платежей в горизонте планирования" in text
