from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import living_minimum as living_repo


async def get_living_minimum_settings(session: AsyncSession, user_id: int):
    return await living_repo.get_or_create_settings(session, user_id)


async def preview_living_minimum_settings(session: AsyncSession, user_id: int) -> dict:
    settings = await living_repo.get_settings(session, user_id)
    if settings is None:
        return {"is_enabled": False, "amount": 0, "period_type": "until_next_income"}
    return {
        "is_enabled": settings.is_enabled,
        "amount": settings.amount,
        "period_type": settings.period_type,
    }


async def enable_living_minimum(session: AsyncSession, user_id: int, amount: int):
    return await living_repo.update_settings(
        session,
        user_id=user_id,
        is_enabled=True,
        amount=amount,
        period_type="until_next_income",
    )


async def disable_living_minimum(session: AsyncSession, user_id: int):
    return await living_repo.update_settings(session, user_id=user_id, is_enabled=False)


async def update_living_minimum_amount(session: AsyncSession, user_id: int, amount: int):
    return await enable_living_minimum(session, user_id, amount)


async def get_living_minimum_summary(session: AsyncSession, user_id: int):
    settings = await living_repo.get_or_create_settings(session, user_id)
    return {"settings": settings}
