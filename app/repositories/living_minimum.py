from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserLivingMinimumSettings


async def get_settings(session: AsyncSession, user_id: int) -> UserLivingMinimumSettings | None:
    return await session.scalar(select(UserLivingMinimumSettings).where(UserLivingMinimumSettings.user_id == user_id))


async def get_or_create_settings(session: AsyncSession, user_id: int) -> UserLivingMinimumSettings:
    settings = await get_settings(session, user_id)
    if settings is not None:
        return settings
    settings = UserLivingMinimumSettings(
        user_id=user_id,
        is_enabled=False,
        amount=0,
        period_type="until_next_income",
    )
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings


async def update_settings(
    session: AsyncSession,
    user_id: int,
    is_enabled: bool | None = None,
    amount: int | None = None,
    period_type: str | None = None,
) -> UserLivingMinimumSettings:
    settings = await get_or_create_settings(session, user_id)
    if is_enabled is not None:
        settings.is_enabled = is_enabled
    if amount is not None:
        settings.amount = amount
    if period_type is not None:
        settings.period_type = period_type
    await session.commit()
    await session.refresh(settings)
    return settings
