from datetime import date

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PaymentRecord


async def create(
    session: AsyncSession,
    user_id: int,
    obligation_id: int,
    amount: int,
    paid_at: date,
    comment: str | None = None,
    period_date: date | None = None,
) -> PaymentRecord:
    record = PaymentRecord(
        user_id=user_id,
        obligation_id=obligation_id,
        amount=amount,
        paid_at=paid_at,
        period_date=period_date,
        comment=comment,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def sum_paid_for_obligation(session: AsyncSession, obligation_id: int) -> int:
    return await session.scalar(select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(PaymentRecord.obligation_id == obligation_id)) or 0


async def sum_paid_for_obligation_period(session: AsyncSession, obligation_id: int, start: date | None, end: date) -> int:
    if start is None:
        period_paid = await session.scalar(
            select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.obligation_id == obligation_id,
                PaymentRecord.period_date == end,
            )
        )
        if period_paid:
            return period_paid
    period_start = start or date(end.year, end.month, 1)
    stmt = select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
        PaymentRecord.obligation_id == obligation_id,
        PaymentRecord.paid_at >= period_start,
        PaymentRecord.paid_at <= end,
    )
    return await session.scalar(stmt) or 0


async def sum_paid_by_user(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(PaymentRecord.user_id == user_id)) or 0


async def list_by_user(session: AsyncSession, user_id: int) -> list[PaymentRecord]:
    result = await session.scalars(select(PaymentRecord).where(PaymentRecord.user_id == user_id).order_by(PaymentRecord.paid_at.desc()))
    return list(result)


async def delete_by_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(sa_delete(PaymentRecord).where(PaymentRecord.user_id == user_id))
    return result.rowcount or 0
