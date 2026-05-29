from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import obligations as obligations_repo
from app.repositories import payments as payments_repo
from app.repositories import reserves as reserves_repo
from app.utils import add_month


async def create_payment_record(
    session: AsyncSession,
    user_id: int,
    obligation_id: int,
    amount: int,
    paid_at: date,
    comment: str | None = None,
):
    obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
    period_date = obligation.next_payment_date if obligation else None
    return await payments_repo.create(session, user_id, obligation_id, amount, paid_at, comment, period_date=period_date)


async def get_active_obligation_for_payment(session: AsyncSession, user_id: int, obligation_id: int):
    obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
    if obligation is None or not obligation.is_active:
        return None
    return obligation


async def process_obligation_payment(session: AsyncSession, user_id: int, obligation_id: int, amount: int, paid_at: date):
    obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
    if obligation is None:
        return None

    period_date = obligation.next_payment_date
    await payments_repo.create(session, user_id, obligation_id, amount, paid_at, period_date=period_date)

    if obligation.total_debt_amount is not None:
        obligation.total_debt_amount = max(0, obligation.total_debt_amount - amount)

    paid_for_period = await payments_repo.sum_paid_for_obligation_period(session, obligation.id, None, period_date)
    if obligation.is_recurring and paid_for_period >= obligation.monthly_payment_amount:
        obligation.next_payment_date = add_month(obligation.next_payment_date, obligation.payment_day)
        obligation.is_active = True
    elif not obligation.is_recurring and paid_for_period >= obligation.monthly_payment_amount:
        obligation.is_active = False

    reserved = await reserves_repo.sum_reserved_for_obligation_period(session, user_id, obligation.id, period_date)
    if reserved > 0:
        await reserves_repo.release_for_obligation(
            session,
            user_id,
            obligation.id,
            min(reserved, amount),
            "Резерв использован при оплате",
            period_date=period_date,
        )

    await session.commit()
    await session.refresh(obligation)
    return obligation
