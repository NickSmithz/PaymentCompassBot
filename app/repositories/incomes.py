from datetime import date, timedelta

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Income


async def create(session: AsyncSession, user_id: int, data: dict) -> Income:
    income = Income(user_id=user_id, **data)
    session.add(income)
    await session.commit()
    await session.refresh(income)
    return income


async def get_by_id(session: AsyncSession, user_id: int, income_id: int) -> Income | None:
    return await session.scalar(select(Income).where(Income.id == income_id, Income.user_id == user_id))


async def list_by_user(session: AsyncSession, user_id: int) -> list[Income]:
    result = await session.scalars(select(Income).where(Income.user_id == user_id).order_by(Income.income_date.desc()))
    return list(result)


async def list_received_by_date(session: AsyncSession, user_id: int, income_date: date) -> list[Income]:
    result = await session.scalars(
        select(Income)
        .where(
            Income.user_id == user_id,
            Income.status == "received",
            Income.income_date == income_date,
        )
        .order_by(Income.id.asc())
    )
    return list(result)


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
    current_date = today or date.today()
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
