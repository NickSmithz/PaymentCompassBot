from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import incomes as incomes_repo
from app.repositories import reserves as reserves_repo


async def get_spending_summary(session: AsyncSession, user_id: int, today: date) -> dict:
    today_incomes = await incomes_repo.list_received_by_date(session, user_id, today)
    if len(today_incomes) > 1:
        return _build_summary("today_multiple", [await _income_summary(session, user_id, income) for income in today_incomes])

    if len(today_incomes) == 1:
        return _build_summary("single_income", [await _income_summary(session, user_id, today_incomes[0])])

    last_income = await incomes_repo.get_last_received(session, user_id, days=60, today=today)
    if last_income is not None:
        return _build_summary("last_income", [await _income_summary(session, user_id, last_income)])

    return {
        "type": "no_income",
        "incomes": [],
        "total_income": 0,
        "total_reserved": 0,
        "total_safe_to_spend": 0,
    }


async def _income_summary(session: AsyncSession, user_id: int, income) -> dict:
    reserved_amount = await reserves_repo.sum_reserved_for_income(session, user_id, income.id)
    return {
        "income_id": income.id,
        "title": income.title,
        "amount": income.amount,
        "income_date": income.income_date,
        "reserved_amount": reserved_amount,
        "safe_to_spend": max(0, income.amount - reserved_amount),
        "items": [],
    }


def _build_summary(summary_type: str, incomes: list[dict]) -> dict:
    return {
        "type": summary_type,
        "incomes": incomes,
        "total_income": sum(item["amount"] for item in incomes),
        "total_reserved": sum(item["reserved_amount"] for item in incomes),
        "total_safe_to_spend": sum(item["safe_to_spend"] for item in incomes),
    }
