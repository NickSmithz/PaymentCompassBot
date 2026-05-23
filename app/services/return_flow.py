from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Income, Obligation, PaymentRecord, ReserveTransaction
from app.utils import add_month

RETURN_FLOW_PAYMENT_COMMENT = "Автоматически отмечено при возврате пользователя"


async def get_return_preview(session: AsyncSession, user_id: int, today: date) -> dict:
    overdue_obligations = await _list_overdue_obligations(session, user_id, today)
    past_expected_incomes = await _list_past_expected_incomes(session, user_id, today)
    return {
        "overdue_obligations_count": len(overdue_obligations),
        "past_expected_incomes_count": len(past_expected_incomes),
        "overdue_obligations": overdue_obligations,
        "past_expected_incomes": past_expected_incomes,
    }


async def apply_return_flow(session: AsyncSession, user_id: int, today: date) -> dict:
    overdue_obligations = await _list_overdue_obligations(session, user_id, today)
    past_expected_incomes = await _list_past_expected_incomes(session, user_id, today)

    payment_records_created = []
    obligations_moved = []
    one_time_obligations_deactivated = []
    payments_marked_paid = 0
    reserve_count_before = await _reserve_count(session, user_id)

    for obligation in overdue_obligations:
        paid_amount = await _sum_paid_for_obligation_return_period(session, obligation.id, obligation.next_payment_date, today)
        amount_to_pay = max(0, obligation.monthly_payment_amount - paid_amount)
        if amount_to_pay > 0:
            record = PaymentRecord(
                user_id=user_id,
                obligation_id=obligation.id,
                amount=amount_to_pay,
                paid_at=today,
                comment=RETURN_FLOW_PAYMENT_COMMENT,
            )
            session.add(record)
            payment_records_created.append(record)
            if obligation.total_debt_amount is not None:
                obligation.total_debt_amount = max(0, obligation.total_debt_amount - amount_to_pay)

        payments_marked_paid += 1
        if obligation.is_recurring:
            old_date = obligation.next_payment_date
            while obligation.next_payment_date < today:
                obligation.next_payment_date = add_month(obligation.next_payment_date, obligation.payment_day)
            obligations_moved.append({"obligation": obligation, "old_date": old_date, "new_date": obligation.next_payment_date})
        else:
            obligation.is_active = False
            one_time_obligations_deactivated.append(obligation)

    for income in past_expected_incomes:
        income.status = "received"

    await session.commit()
    for record in payment_records_created:
        await session.refresh(record)
    for obligation in overdue_obligations:
        await session.refresh(obligation)
    for income in past_expected_incomes:
        await session.refresh(income)

    reserve_count_after = await _reserve_count(session, user_id)

    return {
        "payments_marked_paid": payments_marked_paid,
        "payment_records_created": payment_records_created,
        "obligations_moved": obligations_moved,
        "one_time_obligations_deactivated": one_time_obligations_deactivated,
        "incomes_marked_received": len(past_expected_incomes),
        "incomes": past_expected_incomes,
        "reserve_transactions_created": reserve_count_after - reserve_count_before,
    }


async def _list_overdue_obligations(session: AsyncSession, user_id: int, today: date) -> list[Obligation]:
    result = await session.scalars(
        select(Obligation)
        .where(
            Obligation.user_id == user_id,
            Obligation.is_active.is_(True),
            Obligation.next_payment_date < today,
        )
        .order_by(Obligation.next_payment_date, Obligation.id)
    )
    return list(result)


async def _list_past_expected_incomes(session: AsyncSession, user_id: int, today: date) -> list[Income]:
    result = await session.scalars(
        select(Income)
        .where(
            Income.user_id == user_id,
            Income.status == "expected",
            Income.income_date < today,
        )
        .order_by(Income.income_date, Income.id)
    )
    return list(result)


async def _sum_paid_for_obligation_return_period(
    session: AsyncSession,
    obligation_id: int,
    payment_date: date,
    today: date,
) -> int:
    period_start = date(payment_date.year, payment_date.month, 1)
    return (
        await session.scalar(
            select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.obligation_id == obligation_id,
                PaymentRecord.paid_at >= period_start,
                PaymentRecord.paid_at <= today,
            )
        )
        or 0
    )


async def _reserve_count(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(func.count(ReserveTransaction.id)).where(ReserveTransaction.user_id == user_id)) or 0
