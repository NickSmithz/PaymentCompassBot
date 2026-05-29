from datetime import date, timedelta

from app.calculations import (
    AllocationItem,
    AllocationResult,
    IncomeCalculationDTO,
    ObligationCalculationDTO,
    calculate_income_allocation,
    calculate_purchase_impact,
    calculate_reserved_adjustment,
    calculate_reserved_balance,
    calculate_reserve_to_create,
    normalize_allocation_totals,
)
from app.formatters import format_allocation_result


def income(id_: int, title: str, amount_rub: int, day: date, status: str = "received"):
    return IncomeCalculationDTO(id=id_, title=title, amount=amount_rub * 100, income_date=day, status=status)


def obligation(id_: int, title: str, amount_rub: int, due: date, priority: int = 3, reserved: int = 0, paid: int = 0):
    return ObligationCalculationDTO(
        id=id_,
        title=title,
        type="credit",
        monthly_payment_amount=amount_rub * 100,
        next_payment_date=due,
        priority=priority,
        reserved_amount=reserved * 100,
        paid_amount=paid * 100,
        is_recurring=True,
    )


def test_single_credit_single_income_before_next_income():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Аванс", 35000, today),
        [obligation(1, "Кредит Сбер", 12500, today + timedelta(days=5))],
        [],
        today,
    )
    assert result.total_to_reserve == 12500 * 100
    assert result.safe_to_spend == 22500 * 100


def test_single_credit_two_incomes_before_payment_split_roughly_half():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Аванс", 30000, today),
        [obligation(1, "Кредит", 20000, today + timedelta(days=10))],
        [income(2, "Зарплата", 30000, today + timedelta(days=5), "expected")],
        today,
    )
    assert result.total_to_reserve == 10000 * 100
    assert result.safe_to_spend == 20000 * 100


def test_overdue_payment_high_risk_and_max_reserve():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 10000, today),
        [obligation(1, "Просрочка", 15000, today - timedelta(days=1))],
        [],
        today,
    )
    assert result.items[0].risk == "high"
    assert result.overall_risk == "high"
    assert result.total_to_reserve == 10000 * 100


def test_multiple_payments_nearest_gets_priority():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 15000, today),
        [
            obligation(1, "Дальний", 10000, today + timedelta(days=20)),
            obligation(2, "Ближайший", 10000, today + timedelta(days=4)),
        ],
        [],
        today,
    )
    assert result.items[0].title == "Ближайший"
    assert result.items[0].recommended_reserve == 10000 * 100


def test_payments_are_sorted_by_urgency_buckets():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 50000, today),
        [
            obligation(1, "Дальше недели", 1000, today + timedelta(days=10)),
            obligation(2, "До недели", 1000, today + timedelta(days=5)),
            obligation(3, "До трёх дней", 1000, today + timedelta(days=2)),
            obligation(4, "Просрочен", 1000, today - timedelta(days=1)),
        ],
        [],
        today,
    )
    assert [item.title for item in result.items] == [
        "Просрочен",
        "До трёх дней",
        "До недели",
        "Дальше недели",
    ]


def test_not_enough_income_high_risk_and_reserve_all_income():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 10000, today),
        [obligation(1, "Большой платёж", 50000, today + timedelta(days=2))],
        [],
        today,
    )
    assert result.overall_risk == "high"
    assert result.total_to_reserve == 10000 * 100
    assert result.safe_to_spend == 0


def test_purchase_impact_safe_purchase():
    result = calculate_purchase_impact(
        purchase_amount=5000 * 100,
        safe_to_spend=20000 * 100,
        days_until_next_income=10,
        living_minimum_enabled=True,
        living_minimum_amount=10000 * 100,
        overall_risk="low",
    )
    assert result.recommendation_type == "can_buy"
    assert result.safe_to_spend_after == 15000 * 100
    assert result.risk_after == "low"


def test_purchase_impact_breaks_living_minimum():
    result = calculate_purchase_impact(
        purchase_amount=9000 * 100,
        safe_to_spend=20000 * 100,
        days_until_next_income=10,
        living_minimum_enabled=True,
        living_minimum_amount=15000 * 100,
        overall_risk="low",
    )
    assert result.recommendation_type == "be_careful"
    assert result.living_gap_after == 4000 * 100


def test_purchase_impact_more_than_free_money():
    result = calculate_purchase_impact(
        purchase_amount=15000 * 100,
        safe_to_spend=10000 * 100,
        days_until_next_income=5,
        living_minimum_enabled=False,
        living_minimum_amount=0,
        overall_risk="low",
    )
    assert result.recommendation_type == "better_not"
    assert result.overspend_amount == 5000 * 100
    assert result.risk_after == "high"


def test_purchase_impact_without_next_income_warns():
    result = calculate_purchase_impact(
        purchase_amount=1000 * 100,
        safe_to_spend=10000 * 100,
        days_until_next_income=None,
        living_minimum_enabled=False,
        living_minimum_amount=0,
        overall_risk="low",
    )
    assert result.daily_limit_after is None
    assert any("Следующий доход не указан" in warning for warning in result.warnings)


def test_purchase_impact_existing_high_risk_stays_high():
    result = calculate_purchase_impact(
        purchase_amount=1000 * 100,
        safe_to_spend=10000 * 100,
        days_until_next_income=5,
        living_minimum_enabled=False,
        living_minimum_amount=0,
        overall_risk="high",
    )
    assert result.risk_after == "high"
    assert result.recommendation_type in {"better_not", "be_careful"}
    assert any("Риск просрочки уже высокий" in warning for warning in result.warnings)


def test_reserved_adjustment_increase():
    result = calculate_reserved_adjustment(current_reserved=7000, new_reserved=10000)
    assert result == {"delta": 3000, "transaction_type": "manual_adjustment", "amount": 3000}


def test_reserved_adjustment_decrease():
    result = calculate_reserved_adjustment(current_reserved=10000, new_reserved=6000)
    assert result == {"delta": -4000, "transaction_type": "release", "amount": 4000}


def test_reserved_adjustment_unchanged():
    result = calculate_reserved_adjustment(current_reserved=7000, new_reserved=7000)
    assert result == {"delta": 0, "transaction_type": "none", "amount": 0}

def test_allocation_uses_existing_reserved_amount_from_previous_income():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(2, "Второй доход", 25000, today),
        [obligation(1, "Кредитка ТБанк", 1500, today + timedelta(days=5), reserved=740)],
        [],
        today,
    )
    assert len(result.items) == 1
    assert result.items[0].remaining_amount == 760 * 100
    assert result.items[0].recommended_reserve <= 760 * 100
    assert result.items[0].recommended_reserve != 1500 * 100


def test_allocation_skips_obligation_fully_covered_by_reserve():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(2, "Второй доход", 25000, today),
        [obligation(1, "Манимэн", 5600, today + timedelta(days=5), reserved=5600)],
        [],
        today,
    )
    assert result.items == []
    assert result.total_to_reserve == 0
    assert result.safe_to_spend == 25000 * 100


def test_allocation_uses_existing_paid_amount_for_current_period():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(2, "Второй доход", 25000, today),
        [obligation(1, "Частично оплачен", 7500, today + timedelta(days=5), reserved=2913, paid=1500)],
        [],
        today,
    )
    assert len(result.items) == 1
    assert result.items[0].remaining_amount == 3087 * 100
    assert result.items[0].recommended_reserve <= 3087 * 100


def test_reserved_balance_release_decreases_reserve():
    reserved = calculate_reserved_balance(
        [
            {"transaction_type": "reserve", "amount": 5000},
            {"transaction_type": "release", "amount": 2000},
        ]
    )
    assert reserved == 3000


def test_second_income_reserves_only_remaining_after_first_income():
    today = date(2026, 5, 8)
    first = calculate_income_allocation(
        income(1, "Первый доход", 30000, today),
        [obligation(1, "Кредитка ТБанк", 1500, today + timedelta(days=10))],
        [income(2, "Второй доход", 25000, today + timedelta(days=5), "expected")],
        today,
    )
    first_reserved = first.items[0].recommended_reserve
    assert first_reserved > 0

    second = calculate_income_allocation(
        income(2, "Второй доход", 25000, today + timedelta(days=5)),
        [
            ObligationCalculationDTO(
                id=1,
                title="Кредитка ТБанк",
                type="credit",
                monthly_payment_amount=1500 * 100,
                next_payment_date=today + timedelta(days=10),
                priority=3,
                reserved_amount=first_reserved,
                paid_amount=0,
                is_recurring=True,
            )
        ],
        [],
        today,
    )
    assert second.items[0].recommended_reserve <= 1500 * 100 - first_reserved

def test_reserve_to_create_is_capped_by_current_remaining():
    assert calculate_reserve_to_create(recommended_reserve=1500 * 100, current_remaining=760 * 100) == 760 * 100
    assert calculate_reserve_to_create(recommended_reserve=1500 * 100, current_remaining=0) == 0


def test_recommended_reserve_is_not_more_than_current_income_remaining():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 5000, today),
        [obligation(1, "Большой платёж", 12000, today + timedelta(days=5))],
        [],
        today,
    )
    assert result.total_to_reserve == 5000 * 100
    assert result.items[0].recommended_reserve == 5000 * 100


def test_future_income_after_due_date_is_not_used_for_payment():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Аванс", 10000, today),
        [obligation(1, "Платёж", 20000, today + timedelta(days=5))],
        [income(2, "Зарплата", 30000, today + timedelta(days=10), "expected")],
        today,
    )
    assert result.total_to_reserve == 10000 * 100
    assert result.items[0].recommended_reserve == 10000 * 100


def test_last_income_before_due_reserves_all_current_income_when_not_enough():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 20000, today),
        [obligation(1, "Платёж", 25000, today + timedelta(days=20))],
        [],
        today,
    )
    assert result.items[0].recommended_reserve == 20000 * 100


def test_last_income_before_due_reserves_full_remaining_when_enough():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 30000, today),
        [obligation(1, "Платёж", 25000, today + timedelta(days=20))],
        [],
        today,
    )
    assert result.items[0].recommended_reserve == 25000 * 100


def test_future_income_keeps_proportional_allocation():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 30000, today),
        [obligation(1, "Платёж", 20000, today + timedelta(days=20))],
        [income(2, "Будущий доход", 30000, today + timedelta(days=10), "expected")],
        today,
    )
    assert result.items[0].recommended_reserve == 10000 * 100


def test_urgent_payment_with_future_income_keeps_proportional_allocation():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 10000, today),
        [obligation(1, "Скорый платёж", 10000, today + timedelta(days=2))],
        [income(2, "Будущий доход", 10000, today + timedelta(days=1), "expected")],
        today,
    )
    assert result.items[0].recommended_reserve == 5000 * 100


def test_distant_payment_gets_reserve_after_urgent_payment_when_money_remains():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 30000, today),
        [
            obligation(1, "Дальний платёж", 15000, today + timedelta(days=20)),
            obligation(2, "Срочный платёж", 10000, today + timedelta(days=2)),
        ],
        [],
        today,
    )
    assert result.items[0].title == "Срочный платёж"
    assert result.items[0].recommended_reserve == 10000 * 100
    assert result.items[1].title == "Дальний платёж"
    assert result.items[1].recommended_reserve == 15000 * 100


def test_closed_payment_is_not_included_in_allocation_items():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 30000, today),
        [obligation(1, "Закрытый платёж", 25000, today + timedelta(days=20), reserved=25000)],
        [],
        today,
    )
    assert result.items == []


def test_warning_when_no_future_income_before_due_and_money_still_missing():
    today = date(2026, 5, 8)
    result = calculate_income_allocation(
        income(1, "Доход", 20000, today),
        [obligation(1, "Аренда Кв", 25000, date(2026, 6, 5))],
        [],
        today,
    )
    assert result.items[0].recommended_reserve == 20000 * 100
    assert any(
        "До платежа «Аренда Кв» может не хватить денег: до 05.06.2026 больше нет ожидаемых доходов."
        in warning
        for warning in result.warnings
    )


def _allocation_item(amount_rub: int, obligation_id: int = 1) -> AllocationItem:
    due = date(2026, 7, 30)
    return AllocationItem(
        obligation_id=obligation_id,
        title=f"Payment {obligation_id}",
        due_date=due,
        period_date=due,
        required_amount=amount_rub * 100,
        remaining_amount=amount_rub * 100,
        recommended_reserve=amount_rub * 100,
        risk="low",
    )


def test_allocation_totals_use_sum_of_displayed_items_yunona_case():
    result = AllocationResult(
        income_id=1,
        income_title="Юнона",
        income_amount=30000 * 100,
        total_to_reserve=0,
        safe_to_spend=0,
        overall_risk="low",
        items=[
            _allocation_item(1695, 1),
            _allocation_item(111, 2),
            _allocation_item(1481, 3),
            _allocation_item(515, 4),
            _allocation_item(95, 5),
            _allocation_item(1029, 6),
        ],
    )

    normalize_allocation_totals(result)

    assert result.total_to_reserve == 4926 * 100
    assert result.safe_to_spend == 25074 * 100
    assert result.total_to_reserve + result.safe_to_spend == result.income_amount


def test_allocation_totals_use_sum_of_displayed_items_yazdorov_case():
    result = AllocationResult(
        income_id=1,
        income_title="ЯЗдоров",
        income_amount=48000 * 100,
        total_to_reserve=0,
        safe_to_spend=0,
        overall_risk="low",
        items=[
            _allocation_item(4302, 1),
            _allocation_item(281, 2),
            _allocation_item(3328, 3),
            _allocation_item(1094, 4),
            _allocation_item(203, 5),
            _allocation_item(2093, 6),
        ],
    )

    normalize_allocation_totals(result)

    assert result.total_to_reserve == 11301 * 100
    assert result.safe_to_spend == 36699 * 100
    assert result.total_to_reserve + result.safe_to_spend == result.income_amount


def test_allocation_totals_floor_item_kopeks_to_user_visible_rubles():
    due = date(2026, 7, 30)
    result = AllocationResult(
        income_id=1,
        income_title="Доход",
        income_amount=30000 * 100,
        total_to_reserve=0,
        safe_to_spend=0,
        overall_risk="low",
        items=[
            AllocationItem(1, "A", due, due, 2000 * 100, 2000 * 100, 1695 * 100 + 99, "low"),
            AllocationItem(2, "B", due, due, 2000 * 100, 2000 * 100, 111 * 100 + 99, "low"),
        ],
    )

    normalize_allocation_totals(result)

    assert [item.recommended_reserve for item in result.items] == [1695 * 100, 111 * 100]
    assert result.total_to_reserve == 1806 * 100
    assert result.safe_to_spend == 28194 * 100


def test_allocation_totals_do_not_make_negative_safe_to_spend():
    result = AllocationResult(
        income_id=1,
        income_title="Доход",
        income_amount=10000 * 100,
        total_to_reserve=0,
        safe_to_spend=0,
        overall_risk="low",
        items=[_allocation_item(12000, 1)],
    )

    normalize_allocation_totals(result)

    assert result.total_to_reserve == 10000 * 100
    assert result.items[0].recommended_reserve == 10000 * 100
    assert result.safe_to_spend == 0


def test_allocation_formatter_total_matches_displayed_items():
    result = AllocationResult(
        income_id=1,
        income_title="Юнона",
        income_amount=30000 * 100,
        total_to_reserve=4929 * 100,
        safe_to_spend=25070 * 100,
        overall_risk="low",
        items=[
            _allocation_item(1695, 1),
            _allocation_item(111, 2),
            _allocation_item(1481, 3),
            _allocation_item(515, 4),
            _allocation_item(95, 5),
            _allocation_item(1029, 6),
        ],
    )

    text = format_allocation_result(result)

    assert "Нужно отложить на платежи: 4 926 ₽" in text
    assert "Можно тратить: 25 074 ₽" in text
