from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import users as users_repo


async def get_or_create_user_from_telegram(session: AsyncSession, telegram_id: int, username: str | None, first_name: str | None):
    user = await users_repo.get_by_telegram_id(session, telegram_id)
    if user:
        updates = {}
        if user.username != username:
            updates["username"] = username
        if user.first_name != first_name:
            updates["first_name"] = first_name
        return await users_repo.update_user(session, user, updates) if updates else user
    return await users_repo.create_user(session, telegram_id, username, first_name)


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int):
    return await users_repo.get_by_telegram_id(session, telegram_id)


async def update_user_settings(session: AsyncSession, user_id: int, **data):
    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        return None
    return await users_repo.update_user(session, user, data)
