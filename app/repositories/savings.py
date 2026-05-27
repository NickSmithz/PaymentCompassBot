from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Income, SavingsTransaction, UserSavingsSettings


async def get_settings(session: AsyncSession, user_id: int) -> UserSavingsSettings | None:
    return await session.scalar(select(UserSavingsSettings).where(UserSavingsSettings.user_id == user_id))


async def get_or_create_settings(session: AsyncSession, user_id: int) -> UserSavingsSettings:
    settings = await get_settings(session, user_id)
    if settings is not None:
        return settings
    settings = UserSavingsSettings(user_id=user_id, is_enabled=False, percent=10)
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings


async def update_settings(
    session: AsyncSession,
    user_id: int,
    is_enabled: bool | None = None,
    percent: int | None = None,
) -> UserSavingsSettings:
    settings = await get_or_create_settings(session, user_id)
    if is_enabled is not None:
        settings.is_enabled = is_enabled
    if percent is not None:
        settings.percent = percent
    await session.commit()
    await session.refresh(settings)
    return settings


async def create_transaction(
    session: AsyncSession,
    user_id: int,
    income_id: int | None,
    amount: int,
    transaction_type: str,
    comment: str | None = None,
) -> SavingsTransaction:
    tx = SavingsTransaction(
        user_id=user_id,
        income_id=income_id,
        amount=amount,
        transaction_type=transaction_type,
        comment=comment,
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def list_transactions(session: AsyncSession, user_id: int, limit: int | None = None):
    stmt = (
        select(SavingsTransaction, Income)
        .outerjoin(Income, Income.id == SavingsTransaction.income_id)
        .where(SavingsTransaction.user_id == user_id)
        .order_by(SavingsTransaction.created_at.desc(), SavingsTransaction.id.desc())
    )
    if limit:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.all())


async def list_by_income(session: AsyncSession, user_id: int, income_id: int) -> list[SavingsTransaction]:
    result = await session.scalars(
        select(SavingsTransaction).where(
            SavingsTransaction.user_id == user_id,
            SavingsTransaction.income_id == income_id,
        )
    )
    return list(result)


async def has_savings_for_income(session: AsyncSession, user_id: int, income_id: int) -> bool:
    existing = await session.scalar(
        select(SavingsTransaction.id).where(
            SavingsTransaction.user_id == user_id,
            SavingsTransaction.income_id == income_id,
            SavingsTransaction.transaction_type == "save",
        )
    )
    return existing is not None


async def release_by_income(session: AsyncSession, user_id: int, income_id: int) -> list[SavingsTransaction]:
    transactions = await list_by_income(session, user_id, income_id)
    saved = sum(tx.amount for tx in transactions if tx.transaction_type == "save")
    released = sum(tx.amount for tx in transactions if tx.transaction_type == "release")
    amount_to_release = max(0, saved - released)
    if amount_to_release <= 0:
        return []
    tx = await create_transaction(
        session,
        user_id=user_id,
        income_id=income_id,
        amount=amount_to_release,
        transaction_type="release",
        comment="Отмена накопления по доходу",
    )
    return [tx]


async def get_total_savings(session: AsyncSession, user_id: int) -> int:
    saved = await session.scalar(
        select(func.coalesce(func.sum(SavingsTransaction.amount), 0)).where(
            SavingsTransaction.user_id == user_id,
            SavingsTransaction.transaction_type.in_(["save", "manual_adjustment"]),
        )
    )
    released = await session.scalar(
        select(func.coalesce(func.sum(SavingsTransaction.amount), 0)).where(
            SavingsTransaction.user_id == user_id,
            SavingsTransaction.transaction_type == "release",
        )
    )
    return max(0, (saved or 0) - (released or 0))


async def delete_transactions_by_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(sa_delete(SavingsTransaction).where(SavingsTransaction.user_id == user_id))
    return result.rowcount or 0


async def delete_settings_by_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(sa_delete(UserSavingsSettings).where(UserSavingsSettings.user_id == user_id))
    return result.rowcount or 0
