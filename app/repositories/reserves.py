from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReserveTransaction


async def create(session: AsyncSession, user_id: int, obligation_id: int | None, income_id: int | None, amount: int, transaction_type: str, comment: str | None = None) -> ReserveTransaction:
    tx = ReserveTransaction(user_id=user_id, obligation_id=obligation_id, income_id=income_id, amount=amount, transaction_type=transaction_type, comment=comment)
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def bulk_create(session: AsyncSession, transactions: list[dict]) -> list[ReserveTransaction]:
    items = [ReserveTransaction(**data) for data in transactions]
    session.add_all(items)
    await session.commit()
    for item in items:
        await session.refresh(item)
    return items


async def sum_reserved_for_obligation(session: AsyncSession, obligation_id: int) -> int:
    reserve = await session.scalar(
        select(func.coalesce(func.sum(ReserveTransaction.amount), 0)).where(
            ReserveTransaction.obligation_id == obligation_id,
            ReserveTransaction.transaction_type.in_(["reserve", "manual_adjustment"]),
        )
    )
    release = await session.scalar(
        select(func.coalesce(func.sum(ReserveTransaction.amount), 0)).where(
            ReserveTransaction.obligation_id == obligation_id,
            ReserveTransaction.transaction_type == "release",
        )
    )
    return max(0, (reserve or 0) - (release or 0))


async def list_by_income(session: AsyncSession, income_id: int) -> list[ReserveTransaction]:
    result = await session.scalars(select(ReserveTransaction).where(ReserveTransaction.income_id == income_id))
    return list(result)


async def has_reserves_for_income(session: AsyncSession, income_id: int) -> bool:
    existing = await session.scalar(select(ReserveTransaction.id).where(ReserveTransaction.income_id == income_id).limit(1))
    return existing is not None


async def release_for_obligation(session: AsyncSession, user_id: int, obligation_id: int, amount: int, comment: str | None = None) -> ReserveTransaction:
    return await create(session, user_id, obligation_id, None, amount, "release", comment)


async def release_by_income(session: AsyncSession, user_id: int, income_id: int) -> list[ReserveTransaction]:
    reserves = await list_by_income(session, income_id)
    already_released = {
        tx.obligation_id: 0
        for tx in reserves
        if tx.transaction_type == "release" and tx.obligation_id is not None
    }
    for tx in reserves:
        if tx.transaction_type == "release" and tx.obligation_id is not None:
            already_released[tx.obligation_id] = already_released.get(tx.obligation_id, 0) + tx.amount
    amounts: dict[int, int] = {}
    for tx in reserves:
        if tx.transaction_type == "reserve" and tx.obligation_id is not None:
            amounts[tx.obligation_id] = amounts.get(tx.obligation_id, 0) + tx.amount

    releases = []
    for obligation_id, amount in amounts.items():
        amount_to_release = max(0, amount - already_released.get(obligation_id, 0))
        if amount_to_release > 0:
            releases.append(
                ReserveTransaction(
                    user_id=user_id,
                    obligation_id=obligation_id,
                    income_id=income_id,
                    amount=amount_to_release,
                    transaction_type="release",
                    comment="Отмена резерва по доходу",
                )
            )
    if releases:
        session.add_all(releases)
        await session.commit()
        for item in releases:
            await session.refresh(item)
    return releases
