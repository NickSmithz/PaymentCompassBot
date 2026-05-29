from datetime import date
from types import SimpleNamespace

from app.handlers.common import _format_debug_reserve_instance_lines


def test_debug_reserve_instance_lines_include_period_date_and_instance_amounts():
    instance = SimpleNamespace(
        title="Кредит Альфа",
        period_date=date(2026, 7, 30),
        next_payment_date=date(2026, 7, 30),
        monthly_payment_amount=40000_00,
        reserved_amount=32828_00,
        paid_amount=0,
    )

    lines = _format_debug_reserve_instance_lines(instance)

    assert "period_date=2026-07-30" in lines
    assert "reserved_sum=32 828 ₽" in lines
    assert "remaining=7 172 ₽" in lines


def test_debug_reserve_instance_lines_fall_back_to_next_payment_date():
    instance = SimpleNamespace(
        title="Кредитка",
        period_date=None,
        next_payment_date=date(2026, 7, 31),
        monthly_payment_amount=2200_00,
        reserved_amount=1684_00,
        paid_amount=0,
    )

    lines = _format_debug_reserve_instance_lines(instance)

    assert "period_date=2026-07-31" in lines
