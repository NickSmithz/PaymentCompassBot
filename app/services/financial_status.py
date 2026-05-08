from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import incomes as incomes_repo
from app.services import allocation as allocation_service
from app.services import living_minimum as living_service
from app.services import obligations as obligation_service


def _income_summary(income):
    if income is None:
        return None
    return {"title": income.title, "amount": income.amount, "date": income.income_date}


async def get_financial_status(session: AsyncSession, user_id: int, today: date):
    income = await incomes_repo.get_last_received(session, user_id, 60)
    if income is None:
        return {"has_income": False, "recommendations": ["Добавить доход со статусом «Уже пришёл»."]}

    allocation = await allocation_service.recalculate_last_income(session, user_id, today)
    living = await living_service.get_living_minimum_settings(session, user_id)
    obligations_summary = await obligation_service.get_upcoming_obligations_summary(session, user_id, today)
    nearest_obligation = obligations_summary["items"][0] if obligations_summary["items"] else None
    future_incomes = await incomes_repo.list_future_by_user(session, user_id, today)
    next_income = future_incomes[0] if future_incomes else None

    living_gap = max(0, living.amount - allocation.safe_to_spend) if living.is_enabled else 0
    if allocation.overall_risk == "high":
        overall_status = "danger"
    elif living_gap > 0 or allocation.overall_risk == "medium":
        overall_status = "attention"
    else:
        overall_status = "good"

    recommendations = []
    if allocation.total_to_reserve > 0:
        recommendations.append("Отложить деньги на ближайшие платежи.")
    if living.is_enabled:
        recommendations.append("Оставить минимум на жизнь до следующего дохода.")
    if living_gap > 0 and allocation.actual_savings_amount > 0:
        recommendations.append("Временно уменьшить копилку, если не хватает на минимум.")
    if next_income:
        recommendations.append(f"Проверить ожидаемый доход {next_income.income_date.strftime('%d.%m.%Y')}.")
        days = max(1, (next_income.income_date - today).days)
        recommendations.append("Держать дневные траты в пределах плана до следующего дохода.")
    if not recommendations:
        recommendations.append("Не тратить больше свободной суммы.")

    return {
        "has_income": True,
        "income_title": income.title,
        "income_amount": income.amount,
        "income_date": income.income_date,
        "safe_to_spend": allocation.safe_to_spend,
        "total_to_reserve": allocation.total_to_reserve,
        "savings_amount": allocation.actual_savings_amount,
        "savings_enabled": allocation.savings_enabled,
        "living_minimum_enabled": living.is_enabled,
        "living_minimum_amount": living.amount,
        "living_minimum_gap": living_gap,
        "overall_risk": allocation.overall_risk,
        "overall_status": overall_status,
        "nearest_obligation": nearest_obligation,
        "next_income": _income_summary(next_income),
        "recommendations": recommendations,
    }
