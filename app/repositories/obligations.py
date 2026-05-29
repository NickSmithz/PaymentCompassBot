from datetime import date, timedelta

from sqlalchemy import delete as sa_delete, func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Obligation, User


async def create(session: AsyncSession, user_id: int, data: dict) -> Obligation:
    item = Obligation(user_id=user_id, **data)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def get_by_id(session: AsyncSession, user_id: int, obligation_id: int) -> Obligation | None:
    return await session.scalar(select(Obligation).where(Obligation.id == obligation_id, Obligation.user_id == user_id))


async def list_active_by_user(session: AsyncSession, user_id: int) -> list[Obligation]:
    result = await session.scalars(
        select(Obligation).where(Obligation.user_id == user_id, Obligation.is_active.is_(True)).order_by(Obligation.next_payment_date)
    )
    return list(result)


async def list_by_user(session: AsyncSession, user_id: int) -> list[Obligation]:
    result = await session.scalars(
        select(Obligation).where(Obligation.user_id == user_id).order_by(Obligation.next_payment_date)
    )
    return list(result)


async def count_by_user(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(func.count(Obligation.id)).where(Obligation.user_id == user_id)) or 0


async def count_active_by_user(session: AsyncSession, user_id: int) -> int:
    return (
        await session.scalar(
            select(func.count(Obligation.id)).where(
                Obligation.user_id == user_id,
                Obligation.is_active.is_(True),
            )
        )
        or 0
    )


async def update(session: AsyncSession, obligation: Obligation, data: dict) -> Obligation:
    for key, value in data.items():
        setattr(obligation, key, value)
    await session.commit()
    await session.refresh(obligation)
    return obligation


async def deactivate(session: AsyncSession, obligation: Obligation) -> Obligation:
    obligation.is_active = False
    await session.commit()
    await session.refresh(obligation)
    return obligation


async def activate_all_by_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(sa_update(Obligation).where(Obligation.user_id == user_id).values(is_active=True))
    return result.rowcount or 0


async def delete_by_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(sa_delete(Obligation).where(Obligation.user_id == user_id))
    return result.rowcount or 0


async def list_due_for_reminders(session: AsyncSession, today: date) -> list[tuple[Obligation, User]]:
    max_date = today + timedelta(days=7)
    result = await session.execute(
        select(Obligation, User)
        .join(User, User.id == Obligation.user_id)
        .where(Obligation.is_active.is_(True), User.reminders_enabled.is_(True), Obligation.next_payment_date <= max_date)
        .order_by(Obligation.next_payment_date)
    )
    return list(result.all())
