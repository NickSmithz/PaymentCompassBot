from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Income, User


async def create_user(session: AsyncSession, telegram_id: int, username: str | None, first_name: str | None) -> User:
    user = User(telegram_id=telegram_id, username=username, first_name=first_name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def update_last_focus_income_id(session: AsyncSession, user_id: int, income_id: int | None) -> User | None:
    user = await get_by_id(session, user_id)
    if user is None:
        return None
    user.last_focus_income_id = income_id
    await session.commit()
    await session.refresh(user)
    return user


async def clear_last_focus_income(session: AsyncSession, user_id: int) -> User | None:
    return await update_last_focus_income_id(session, user_id, None)


async def clear_return_prompt(session: AsyncSession, user_id: int) -> User | None:
    user = await get_by_id(session, user_id)
    if user is None:
        return None
    user.last_return_prompt_at = None
    await session.commit()
    await session.refresh(user)
    return user


async def get_last_focus_income_id(session: AsyncSession, user_id: int) -> int | None:
    user = await get_by_id(session, user_id)
    return user.last_focus_income_id if user else None


async def get_last_focus_income(session: AsyncSession, user_id: int) -> Income | None:
    income_id = await get_last_focus_income_id(session, user_id)
    if income_id is None:
        return None
    return await session.scalar(select(Income).where(Income.id == income_id, Income.user_id == user_id))


async def update_user(session: AsyncSession, user: User, data: dict) -> User:
    for key, value in data.items():
        setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user
