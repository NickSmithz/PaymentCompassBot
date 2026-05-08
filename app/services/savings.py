from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import savings as savings_repo


async def get_savings_settings(session: AsyncSession, user_id: int):
    return await savings_repo.get_or_create_settings(session, user_id)


async def enable_savings(session: AsyncSession, user_id: int, percent: int = 10):
    return await savings_repo.update_settings(session, user_id, is_enabled=True, percent=percent)


async def disable_savings(session: AsyncSession, user_id: int):
    return await savings_repo.update_settings(session, user_id, is_enabled=False)


async def update_savings_percent(session: AsyncSession, user_id: int, percent: int):
    percent = max(1, min(50, percent))
    return await savings_repo.update_settings(session, user_id, is_enabled=True, percent=percent)


async def process_savings_for_income(
    session: AsyncSession,
    user_id: int,
    income_id: int,
    income_amount: int,
    available_after_payments: int,
):
    settings = await savings_repo.get_or_create_settings(session, user_id)
    if not settings.is_enabled:
        return {
            "is_enabled": False,
            "percent": settings.percent,
            "desired_savings": 0,
            "actual_savings": 0,
        }

    desired_savings = ceil(income_amount * settings.percent / 100)
    actual_savings = min(desired_savings, max(0, available_after_payments))
    existing = await savings_repo.list_by_income(session, user_id, income_id)
    saved = sum(tx.amount for tx in existing if tx.transaction_type == "save")
    released = sum(tx.amount for tx in existing if tx.transaction_type == "release")
    should_create = saved == 0 or released >= saved
    if actual_savings > 0 and should_create:
        await savings_repo.create_transaction(
            session,
            user_id=user_id,
            income_id=income_id,
            amount=actual_savings,
            transaction_type="save",
            comment=f"Копилка {settings.percent}% от дохода",
        )
    return {
        "is_enabled": True,
        "percent": settings.percent,
        "desired_savings": desired_savings,
        "actual_savings": actual_savings,
    }


async def release_savings_for_income(session: AsyncSession, user_id: int, income_id: int):
    return await savings_repo.release_by_income(session, user_id, income_id)


async def get_savings_summary(session: AsyncSession, user_id: int):
    settings = await savings_repo.get_or_create_settings(session, user_id)
    total = await savings_repo.get_total_savings(session, user_id)
    return {"settings": settings, "total_savings": total}


async def get_savings_history(session: AsyncSession, user_id: int, limit: int = 10):
    return await savings_repo.list_transactions(session, user_id, limit)
