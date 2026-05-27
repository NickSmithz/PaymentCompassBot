import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import incomes as incomes_repo
from app.repositories import reserves as reserves_repo
from app.repositories import users as users_repo

logger = logging.getLogger(__name__)


async def get_spending_summary(session: AsyncSession, user_id: int, today: date) -> dict:
    user = await users_repo.get_by_id(session, user_id)
    last_focus_income_id = user.last_focus_income_id if user else None

    today_incomes = await incomes_repo.list_received_by_date(session, user_id, today)
    if len(today_incomes) > 1:
        summary = _build_summary("today_multiple", [await _income_summary(session, user_id, income) for income in today_incomes])
        _log_selection(user_id, summary["type"], today_incomes, last_focus_income_id)
        logger.info(
            "Spending summary today incomes: user_id=%s income_ids=%s",
            user_id,
            [income.id for income in today_incomes],
        )
        return summary

    if len(today_incomes) == 1:
        summary = _build_summary("single_today", [await _income_summary(session, user_id, today_incomes[0])])
        _log_selection(user_id, summary["type"], today_incomes, last_focus_income_id)
        return summary

    if last_focus_income_id is not None:
        focus_income = await incomes_repo.get_by_id_for_user(session, user_id, last_focus_income_id)
        if focus_income is not None and focus_income.status == "received":
            summary = _build_summary("focus_income", [await _income_summary(session, user_id, focus_income)])
            _log_selection(user_id, summary["type"], today_incomes, last_focus_income_id)
            return summary

    last_income = await incomes_repo.get_last_received(session, user_id, days=60, today=today)
    if last_income is not None:
        summary = _build_summary("last_received", [await _income_summary(session, user_id, last_income)])
        _log_selection(user_id, summary["type"], today_incomes, last_focus_income_id)
        return summary

    _log_selection(user_id, "no_income", today_incomes, last_focus_income_id)
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


def _log_selection(user_id: int, summary_type: str, today_incomes: list, last_focus_income_id: int | None) -> None:
    logger.info(
        "Spending summary selection: user_id=%s type=%s today_received_count=%s last_focus_income_id=%s",
        user_id,
        summary_type,
        len(today_incomes),
        last_focus_income_id,
    )
