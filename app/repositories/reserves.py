from sqlalchemy import and_, delete as sa_delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReserveTransaction


AUTO_PLAN_SOURCE = "auto_plan"
MANUAL_SOURCE = "manual"
RELEASE_SOURCE = "release"


def _default_source(transaction_type: str) -> str:
    if transaction_type == "reserve":
        return AUTO_PLAN_SOURCE
    if transaction_type == "manual_adjustment":
        return MANUAL_SOURCE
    return RELEASE_SOURCE


def _auto_plan_filter():
    return or_(
        ReserveTransaction.source == AUTO_PLAN_SOURCE,
        ReserveTransaction.comment == AUTO_PLAN_SOURCE,
        and_(ReserveTransaction.source.is_(None), ReserveTransaction.transaction_type == "reserve"),
    )


async def create(
    session: AsyncSession,
    user_id: int,
    obligation_id: int | None,
    income_id: int | None,
    amount: int,
    transaction_type: str,
    comment: str | None = None,
    source: str | None = None,
) -> ReserveTransaction:
    tx = ReserveTransaction(
        user_id=user_id,
        obligation_id=obligation_id,
        income_id=income_id,
        amount=amount,
        transaction_type=transaction_type,
        source=source or _default_source(transaction_type),
        comment=comment,
    )
    session.add(tx)
    await session.flush()
    return tx


async def bulk_create(session: AsyncSession, transactions: list[dict]) -> list[ReserveTransaction]:
    items = [
        ReserveTransaction(
            **{
                **data,
                "source": data.get("source") or _default_source(data["transaction_type"]),
            }
        )
        for data in transactions
    ]
    session.add_all(items)
    await session.flush()
    return items


async def sum_reserved_for_obligation(
    session: AsyncSession,
    user_id_or_obligation_id: int,
    obligation_id: int | None = None,
    *,
    user_id: int | None = None,
) -> int:
    if obligation_id is None:
        resolved_obligation_id = user_id_or_obligation_id
        resolved_user_id = user_id
    else:
        resolved_obligation_id = obligation_id
        resolved_user_id = user_id if user_id is not None else user_id_or_obligation_id

    reserve_filters = [
        ReserveTransaction.obligation_id == resolved_obligation_id,
        ReserveTransaction.transaction_type.in_(["reserve", "manual_adjustment"]),
    ]
    release_filters = [
        ReserveTransaction.obligation_id == resolved_obligation_id,
        ReserveTransaction.transaction_type == "release",
    ]
    if resolved_user_id is not None:
        reserve_filters.append(ReserveTransaction.user_id == resolved_user_id)
        release_filters.append(ReserveTransaction.user_id == resolved_user_id)

    reserve = await session.scalar(
        select(func.coalesce(func.sum(ReserveTransaction.amount), 0)).where(*reserve_filters)
    )
    release = await session.scalar(
        select(func.coalesce(func.sum(ReserveTransaction.amount), 0)).where(*release_filters)
    )
    return max(0, (reserve or 0) - (release or 0))


async def list_by_income(
    session: AsyncSession,
    income_id: int,
    user_id: int | None = None,
) -> list[ReserveTransaction]:
    filters = [ReserveTransaction.income_id == income_id]
    if user_id is not None:
        filters.append(ReserveTransaction.user_id == user_id)
    result = await session.scalars(
        select(ReserveTransaction).where(*filters).order_by(ReserveTransaction.id.asc())
    )
    return list(result)


async def list_auto_reserves_by_income(
    session: AsyncSession,
    user_id: int,
    income_id: int,
) -> list[ReserveTransaction]:
    result = await session.scalars(
        select(ReserveTransaction)
        .where(
            ReserveTransaction.user_id == user_id,
            ReserveTransaction.income_id == income_id,
            ReserveTransaction.transaction_type == "reserve",
            ReserveTransaction.obligation_id.is_not(None),
            ReserveTransaction.amount > 0,
            _auto_plan_filter(),
        )
        .order_by(ReserveTransaction.id.asc())
    )
    return list(result)


async def list_real_reserves_by_income(
    session: AsyncSession,
    income_id: int,
    user_id: int,
) -> list[ReserveTransaction]:
    return await list_auto_reserves_by_income(session, user_id, income_id)


async def list_by_user(
    session: AsyncSession,
    user_id: int,
    limit: int | None = None,
) -> list[ReserveTransaction]:
    stmt = (
        select(ReserveTransaction)
        .where(ReserveTransaction.user_id == user_id)
        .order_by(ReserveTransaction.id.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.scalars(stmt)
    return list(result)


async def delete_by_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(sa_delete(ReserveTransaction).where(ReserveTransaction.user_id == user_id))
    return result.rowcount or 0


async def has_auto_reserves_for_income(session: AsyncSession, user_id: int, income_id: int) -> bool:
    return await sum_auto_reserved_for_income(session, user_id, income_id) > 0


async def has_reserves_for_income(session: AsyncSession, income_id: int, user_id: int) -> bool:
    return await has_auto_reserves_for_income(session, user_id, income_id)


async def sum_auto_reserved_for_income(session: AsyncSession, user_id: int, income_id: int) -> int:
    reserve = await session.scalar(
        select(func.coalesce(func.sum(ReserveTransaction.amount), 0)).where(
            ReserveTransaction.user_id == user_id,
            ReserveTransaction.income_id == income_id,
            ReserveTransaction.transaction_type == "reserve",
            ReserveTransaction.obligation_id.is_not(None),
            ReserveTransaction.amount > 0,
            _auto_plan_filter(),
        )
    )
    release = await session.scalar(
        select(func.coalesce(func.sum(ReserveTransaction.amount), 0)).where(
            ReserveTransaction.user_id == user_id,
            ReserveTransaction.income_id == income_id,
            ReserveTransaction.transaction_type == "release",
            ReserveTransaction.obligation_id.is_not(None),
            _auto_plan_filter(),
        )
    )
    return max(0, (reserve or 0) - (release or 0))


async def sum_reserved_for_income(session: AsyncSession, user_id: int, income_id: int) -> int:
    return await sum_auto_reserved_for_income(session, user_id, income_id)


async def auto_reserved_by_obligation_for_income(
    session: AsyncSession,
    user_id: int,
    income_id: int,
) -> dict[int, int]:
    rows = await list_by_income(session, income_id, user_id=user_id)
    amounts: dict[int, int] = {}
    for tx in rows:
        if tx.obligation_id is None:
            continue
        is_auto = tx.source == AUTO_PLAN_SOURCE or tx.comment == AUTO_PLAN_SOURCE
        if not is_auto:
            continue
        if tx.transaction_type == "reserve":
            amounts[tx.obligation_id] = amounts.get(tx.obligation_id, 0) + tx.amount
        elif tx.transaction_type == "release":
            amounts[tx.obligation_id] = amounts.get(tx.obligation_id, 0) - tx.amount
    return {obligation_id: max(0, amount) for obligation_id, amount in amounts.items() if amount > 0}


async def release_for_obligation(
    session: AsyncSession,
    user_id: int,
    obligation_id: int,
    amount: int,
    comment: str | None = None,
    source: str | None = None,
) -> ReserveTransaction:
    tx = await create(session, user_id, obligation_id, None, amount, "release", comment, source or MANUAL_SOURCE)
    await session.commit()
    return tx


async def release_auto_reserves_for_income(
    session: AsyncSession,
    user_id: int,
    income_id: int,
) -> list[ReserveTransaction]:
    rows = await list_by_income(session, income_id, user_id=user_id)
    reserve_amounts: dict[int, int] = {}
    release_amounts: dict[int, int] = {}

    for tx in rows:
        if tx.obligation_id is None:
            continue
        is_auto = tx.source == AUTO_PLAN_SOURCE or tx.comment == AUTO_PLAN_SOURCE
        if not is_auto:
            continue
        if tx.transaction_type == "reserve":
            reserve_amounts[tx.obligation_id] = reserve_amounts.get(tx.obligation_id, 0) + tx.amount
        elif tx.transaction_type == "release":
            release_amounts[tx.obligation_id] = release_amounts.get(tx.obligation_id, 0) + tx.amount

    releases = []
    for obligation_id, reserve_sum in reserve_amounts.items():
        release_amount = max(0, reserve_sum - release_amounts.get(obligation_id, 0))
        if release_amount <= 0:
            continue
        releases.append(
            await create(
                session,
                user_id=user_id,
                obligation_id=obligation_id,
                income_id=income_id,
                amount=release_amount,
                transaction_type="release",
                source=AUTO_PLAN_SOURCE,
                comment="Отмена автоматического резерва по доходу",
            )
        )

    if releases:
        await session.commit()
    return releases


async def release_by_income(session: AsyncSession, user_id: int, income_id: int) -> list[ReserveTransaction]:
    return await release_auto_reserves_for_income(session, user_id, income_id)
