from datetime import date, datetime, timedelta

from sqlalchemy import delete as sa_delete, func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Income
from app.services.planning import get_today


async def create(session: AsyncSession, user_id: int, data: dict, commit: bool = True) -> Income:
    income = Income(user_id=user_id, **data)
    session.add(income)
    if commit:
        await session.commit()
        await session.refresh(income)
    else:
        await session.flush()
    return income


async def get_by_id(session: AsyncSession, user_id: int, income_id: int) -> Income | None:
    return await session.scalar(select(Income).where(Income.id == income_id, Income.user_id == user_id))


async def get_by_id_for_user(session: AsyncSession, user_id: int, income_id: int) -> Income | None:
    return await get_by_id(session, user_id, income_id)


async def list_by_user(session: AsyncSession, user_id: int) -> list[Income]:
    result = await session.scalars(
        select(Income).where(Income.user_id == user_id).order_by(Income.income_date.desc(), Income.id.desc())
    )
    return list(result)


async def list_incomes_for_status_change(session: AsyncSession, user_id: int) -> list[Income]:
    result = await session.scalars(
        select(Income)
        .where(
            Income.user_id == user_id,
            Income.status == "expected",
        )
        .order_by(
            func.coalesce(Income.period_date, Income.income_date).asc(),
            Income.income_date.asc(),
            Income.id.asc(),
        )
    )
    return list(result)


async def list_all(session: AsyncSession, user_id: int | None = None) -> list[Income]:
    query = select(Income)
    if user_id is not None:
        query = query.where(Income.user_id == user_id)
    result = await session.scalars(query.order_by(Income.user_id.asc(), Income.income_date.asc(), Income.id.asc()))
    return list(result)


async def list_recurring_roots(session: AsyncSession, user_id: int) -> list[Income]:
    result = await session.scalars(
        select(Income)
        .where(
            Income.user_id == user_id,
            Income.is_recurring.is_(True),
            (Income.parent_income_id.is_(None)) | (Income.parent_income_id == Income.id),
        )
        .order_by(Income.income_date.asc(), Income.id.asc())
    )
    return list(result)


async def exists_income_instance(
    session: AsyncSession,
    user_id: int,
    parent_income_id: int,
    period_date: date,
) -> bool:
    existing = await session.scalar(
        select(Income.id)
        .where(
            Income.user_id == user_id,
            Income.period_date == period_date,
            (Income.parent_income_id == parent_income_id) | (Income.id == parent_income_id),
        )
        .limit(1)
    )
    return existing is not None


async def list_received_by_date(session: AsyncSession, user_id: int, income_date: date) -> list[Income]:
    result = await session.scalars(
        select(Income)
        .where(
            Income.user_id == user_id,
            Income.status == "received",
            Income.income_date == income_date,
        )
        .order_by(Income.income_date.asc(), Income.id.asc())
    )
    return list(result)


async def list_received_by_received_at_range(
    session: AsyncSession,
    user_id: int,
    start_at: datetime,
    end_at: datetime,
) -> list[Income]:
    result = await session.scalars(
        select(Income)
        .where(
            Income.user_id == user_id,
            Income.status == "received",
            Income.received_at.is_not(None),
            Income.received_at >= start_at,
            Income.received_at <= end_at,
        )
        .order_by(Income.received_at.asc(), Income.id.asc())
    )
    return list(result)


async def get_last_received_by_received_at(
    session: AsyncSession,
    user_id: int,
    since: datetime | None = None,
) -> Income | None:
    filters = [
        Income.user_id == user_id,
        Income.status == "received",
        Income.received_at.is_not(None),
    ]
    if since is not None:
        filters.append(Income.received_at >= since)
    return await session.scalar(
        select(Income)
        .where(*filters)
        .order_by(Income.received_at.desc(), Income.id.desc())
    )


async def list_future_by_user(session: AsyncSession, user_id: int, from_date: date) -> list[Income]:
    result = await session.scalars(
        select(Income)
        .where(Income.user_id == user_id, Income.income_date > from_date, Income.status.in_(["expected", "received"]))
        .order_by(Income.income_date)
    )
    return list(result)


async def sum_expected_between(session: AsyncSession, user_id: int, start: date, end: date) -> int:
    return (
        await session.scalar(
            select(func.coalesce(func.sum(Income.amount), 0)).where(
                Income.user_id == user_id,
                Income.status == "expected",
                Income.income_date >= start,
                Income.income_date <= end,
            )
        )
        or 0
    )


async def get_last_received(session: AsyncSession, user_id: int, days: int = 60, today: date | None = None) -> Income | None:
    current_date = today or get_today()
    since = current_date - timedelta(days=days)
    return await session.scalar(
        select(Income)
        .where(Income.user_id == user_id, Income.status == "received", Income.income_date >= since)
        .order_by(Income.income_date.desc(), Income.id.desc())
    )


async def update(session: AsyncSession, income: Income, data: dict) -> Income:
    for key, value in data.items():
        setattr(income, key, value)
    await session.commit()
    await session.refresh(income)
    return income


async def delete(session: AsyncSession, income: Income) -> None:
    await session.execute(sa_delete(Income).where(Income.id == income.id))
    await session.commit()


async def reset_statuses_for_user(session: AsyncSession, user_id: int, status: str = "expected") -> int:
    values = {"status": status}
    if status != "received":
        values["received_at"] = None
    result = await session.execute(sa_update(Income).where(Income.user_id == user_id).values(**values))
    return result.rowcount or 0


async def delete_by_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(sa_delete(Income).where(Income.user_id == user_id))
    return result.rowcount or 0
