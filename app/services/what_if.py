from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations import calculate_purchase_impact
from app.repositories import incomes as incomes_repo
from app.services import allocation as allocation_service
from app.services import living_minimum as living_service
from app.services import obligations as obligation_service
from app.services import salary_plan as salary_plan_service


async def simulate_purchase(session: AsyncSession, user_id: int, purchase_amount: int, today: date):
    income = await incomes_repo.get_last_received(session, user_id, 60)
    if income is None:
        return {"can_calculate": False, "reason": "no_received_income"}

    allocation = await allocation_service.recalculate_last_income(session, user_id, today)
    salary_plan = await salary_plan_service.get_salary_plan(session, user_id, today)
    living = await living_service.get_living_minimum_settings(session, user_id)
    obligations_summary = await obligation_service.get_upcoming_obligations_summary(session, user_id, today)
    nearest = obligations_summary["items"][0] if obligations_summary["items"] else None

    days = salary_plan.get("days_until_next_income") if salary_plan.get("has_next_income") else None
    impact = calculate_purchase_impact(
        purchase_amount=purchase_amount,
        safe_to_spend=allocation.safe_to_spend,
        days_until_next_income=days,
        living_minimum_enabled=living.is_enabled,
        living_minimum_amount=living.amount,
        overall_risk=allocation.overall_risk,
    )

    recommendations = []
    if impact.recommendation_type == "can_buy":
        recommendations.append("Покупка не нарушает план. Но после неё дневной лимит станет ниже.")
    elif impact.recommendation_type == "be_careful":
        recommendations.extend(
            [
                "Отложить покупку до следующего дохода.",
                "Купить дешевле.",
                "Временно уменьшить копилку.",
                "Проверить, есть ли ожидаемый доход раньше.",
            ]
        )
    else:
        recommendations.extend(
            [
                "Отложить покупку.",
                "Уменьшить сумму покупки до свободной суммы.",
                "Сначала закрыть ближайшие обязательные платежи.",
                "Вернуться к покупке после следующего дохода.",
            ]
        )

    next_income = salary_plan.get("next_income") if salary_plan.get("has_next_income") else None
    return {
        "can_calculate": True,
        "purchase_amount": impact.purchase_amount,
        "safe_to_spend_before": impact.safe_to_spend_before,
        "safe_to_spend_after": impact.safe_to_spend_after,
        "overspend_amount": impact.overspend_amount,
        "has_next_income": bool(next_income),
        "next_income_title": next_income["title"] if next_income else None,
        "next_income_amount": next_income["amount"] if next_income else None,
        "next_income_date": next_income["date"] if next_income else None,
        "days_until_next_income": days,
        "daily_limit_before": impact.daily_limit_before,
        "daily_limit_after": impact.daily_limit_after,
        "daily_limit_delta": impact.daily_limit_delta,
        "living_minimum_enabled": living.is_enabled,
        "living_minimum_amount": living.amount if living.is_enabled else 0,
        "living_gap_before": impact.living_gap_before,
        "living_gap_after": impact.living_gap_after,
        "overall_risk_before": allocation.overall_risk,
        "risk_after": impact.risk_after,
        "nearest_obligation_title": nearest["title"] if nearest else None,
        "nearest_obligation_date": nearest["date"] if nearest else None,
        "nearest_obligation_remaining": nearest["remaining_amount"] if nearest else None,
        "recommendation_type": impact.recommendation_type,
        "recommendations": recommendations,
        "warnings": impact.warnings,
    }
