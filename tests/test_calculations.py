from datetime import date, timedelta

from app.calculations import (
    IncomeCalculationDTO,
    ObligationCalculationDTO,
    calculate_income_allocation,
    calculate_purchase_impact,
)


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
