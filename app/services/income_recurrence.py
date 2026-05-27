from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import incomes as incomes_repo
from app.utils import add_month_safe


async def ensure_income_instances(
    session: AsyncSession,
    user_id: int,
    today: date,
    horizon_days: int = 45,
) -> list:
    created = []
    changed = False
    horizon_end = today.toordinal() + horizon_days
    roots = await incomes_repo.list_recurring_roots(session, user_id)
    for root in roots:
        root_id = root.parent_income_id or root.id
        if root.parent_income_id is None:
            root.parent_income_id = root.id
            changed = True
        if root.period_date is None:
            root.period_date = root.income_date
            changed = True

        period_date = root.period_date or root.income_date
        while period_date.toordinal() <= horizon_end:
            if not await incomes_repo.exists_income_instance(session, user_id, root_id, period_date):
                created.append(await _create_instance(session, user_id, root, root_id, period_date))
            period_date = add_month_safe(period_date)

    if created or changed:
        await session.commit()
        for income in created:
            await session.refresh(income)
    return created


async def create_next_income_instance_if_needed(
    session: AsyncSession,
    user_id: int,
    income_id: int,
    today: date,
):
    income = await incomes_repo.get_by_id(session, user_id, income_id)
    if income is None or not income.is_recurring:
        return None

    root_id = income.parent_income_id or income.id
    if income.parent_income_id is None:
        income.parent_income_id = income.id
    if income.period_date is None:
        income.period_date = income.income_date

    next_period = add_month_safe(income.period_date)
    if await incomes_repo.exists_income_instance(session, user_id, root_id, next_period):
        await session.commit()
        return None

    created = await _create_instance(session, user_id, income, root_id, next_period)
    await session.commit()
    await session.refresh(created)
    return created


async def _create_instance(session: AsyncSession, user_id: int, source_income, root_id: int, period_date: date):
    data = {
        "title": source_income.title,
        "amount": source_income.amount,
        "income_date": period_date,
        "period_date": period_date,
        "status": "expected",
        "source": source_income.source,
        "received_at": None,
        "is_recurring": True,
        "recurrence_type": source_income.recurrence_type or "monthly",
        "parent_income_id": root_id,
    }
    return await incomes_repo.create(session, user_id, data, commit=False)
