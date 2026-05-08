from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PaymentRecord


async def create(session: AsyncSession, user_id: int, obligation_id: int, amount: int, paid_at: date, comment: str | None = None) -> PaymentRecord:
    record = PaymentRecord(user_id=user_id, obligation_id=obligation_id, amount=amount, paid_at=paid_at, comment=comment)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def sum_paid_for_obligation(session: AsyncSession, obligation_id: int) -> int:
    return await session.scalar(select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(PaymentRecord.obligation_id == obligation_id)) or 0


async def sum_paid_for_obligation_period(session: AsyncSession, obligation_id: int, start: date | None, end: date) -> int:
    stmt = select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(PaymentRecord.obligation_id == obligation_id, PaymentRecord.paid_at <= end)
    if start:
        stmt = stmt.where(PaymentRecord.paid_at >= start)
    return await session.scalar(stmt) or 0


async def sum_paid_by_user(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(PaymentRecord.user_id == user_id)) or 0


async def list_by_user(session: AsyncSession, user_id: int) -> list[PaymentRecord]:
    result = await session.scalars(select(PaymentRecord).where(PaymentRecord.user_id == user_id).order_by(PaymentRecord.paid_at.desc()))
    return list(result)
