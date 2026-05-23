from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.repositories import users as users_repo

RETURN_THRESHOLD = timedelta(days=14)


async def get_previous_activity(session: AsyncSession, user_id: int) -> datetime | None:
    user = await users_repo.get_by_id(session, user_id)
    return user.last_activity_at if user else None


async def update_user_activity(session: AsyncSession, user_id: int, now: datetime):
    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        return None
    user.last_activity_at = now
    await session.commit()
    await session.refresh(user)
    return user


async def should_show_im_back(session: AsyncSession, user_id: int, now: datetime) -> bool:
    previous_activity = await get_previous_activity(session, user_id)
    if previous_activity is None:
        return False
    previous_activity = _align_datetime(previous_activity, now)
    return now - previous_activity >= RETURN_THRESHOLD


async def should_show_im_back_button(session: AsyncSession, user_id: int, now: datetime) -> bool:
    if get_settings().im_back_always_visible:
        return True
    return await should_show_im_back(session, user_id, now)


async def should_show_return_prompt(session: AsyncSession, user_id: int, now: datetime) -> bool:
    user = await users_repo.get_by_id(session, user_id)
    if user is None or user.last_activity_at is None:
        return False
    last_activity_at = _align_datetime(user.last_activity_at, now)
    if now - last_activity_at < RETURN_THRESHOLD:
        return False
    if user.last_return_prompt_at and _align_datetime(user.last_return_prompt_at, now).date() == now.date():
        return False
    return True


async def mark_return_prompt_shown(session: AsyncSession, user_id: int, now: datetime):
    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        return None
    user.last_return_prompt_at = now
    await session.commit()
    await session.refresh(user)
    return user


def _align_datetime(value: datetime, reference: datetime) -> datetime:
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value
