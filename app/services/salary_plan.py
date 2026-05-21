from math import floor
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import incomes as incomes_repo
from app.services import allocation as allocation_service
from app.services import living_minimum as living_service


def _income_summary(income):
    if income is None:
        return None
    return {"title": income.title, "amount": income.amount, "date": income.income_date}


async def get_salary_plan(session: AsyncSession, user_id: int, today: date):
    current_income = await incomes_repo.get_last_received(session, user_id, 60)
    if current_income is None:
        return {"has_income": False, "has_next_income": False, "recommendations": []}

    future_incomes = await incomes_repo.list_future_by_user(session, user_id, today)
    if not future_incomes:
        return {
            "has_income": True,
            "has_next_income": False,
            "current_income": _income_summary(current_income),
            "recommendations": ["Добавь ожидаемый доход, например зарплату или аванс."],
        }

    next_income = future_incomes[0]
    allocation = await allocation_service.recalculate_last_income(session, user_id, today)
    living = await living_service.preview_living_minimum_settings(session, user_id)
    days = max(1, (next_income.income_date - today).days)
    safe_to_spend = allocation.safe_to_spend if allocation else 0
    daily_limit = floor(safe_to_spend / days)
    living_daily = floor(living["amount"] / days) if living["is_enabled"] else 0
    living_gap = max(0, living["amount"] - safe_to_spend) if living["is_enabled"] else 0

    if safe_to_spend <= 0:
        status = "danger"
    elif living["is_enabled"] and safe_to_spend < living["amount"]:
        status = "attention"
    else:
        status = "good"

    recommendations = []
    if status == "good":
        recommendations.append("Старайся держать траты в пределах дневного лимита до следующего дохода.")
    elif status == "attention":
        recommendations.extend(["Уменьшить копилку на этот период.", "Пересмотреть необязательные траты.", "Добавить ожидаемый доход, если он есть."])
    else:
        recommendations.append("Сначала нужно закрыть ближайшие обязательные платежи.")

    return {
        "has_income": True,
        "has_next_income": True,
        "current_income": _income_summary(current_income),
        "next_income": _income_summary(next_income),
        "safe_to_spend": safe_to_spend,
        "days_until_next_income": days,
        "daily_limit": daily_limit,
        "living_minimum_enabled": living["is_enabled"],
        "living_minimum_amount": living["amount"],
        "living_minimum_daily": living_daily,
        "living_minimum_gap": living_gap,
        "status": status,
        "recommendations": recommendations,
    }
