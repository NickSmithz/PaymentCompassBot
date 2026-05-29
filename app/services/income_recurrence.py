import logging
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import incomes as incomes_repo
from app.utils import add_month_safe

logger = logging.getLogger(__name__)


async def ensure_income_instances(
    session: AsyncSession,
    user_id: int,
    today: date,
    horizon_days: int = 45,
) -> list:
    created = []
    changed = False
    horizon_end = today + timedelta(days=horizon_days)
    await normalize_recurring_income_roots(session, user_id)
    roots = await incomes_repo.list_recurring_roots(session, user_id)
    for root in roots:
        created_before = len(created)
        root_id = root.parent_income_id or root.id
        if root.parent_income_id is None:
            root.parent_income_id = root.id
            changed = True
        if root.period_date is None:
            root.period_date = root.income_date
            changed = True

        period_date = root.period_date or root.income_date
        while period_date <= horizon_end:
            if not await incomes_repo.exists_income_instance(session, user_id, root_id, period_date):
                created.append(await _create_instance(session, user_id, root, root_id, period_date))
            period_date = add_month_safe(period_date)
        logger.info(
            "Ensure income instances: root_id=%s title=%s horizon_end=%s created_count=%s",
            root.id,
            root.title,
            horizon_end,
            len(created) - created_before,
        )

    if created or changed:
        await session.commit()
        for income in created:
            await session.refresh(income)
    return created


async def normalize_recurring_income_roots(session: AsyncSession, user_id: int | None = None) -> int:
    incomes = await incomes_repo.list_all(session, user_id)
    changed_count = 0
    for income in incomes:
        should_be_recurring = income.is_recurring or income.recurrence_type == "monthly"
        if not should_be_recurring:
            if income.period_date is None:
                income.period_date = income.income_date
                changed_count += 1
            continue

        old_is_recurring = income.is_recurring
        old_recurrence_type = income.recurrence_type
        old_parent_income_id = income.parent_income_id
        changed = False
        if not income.is_recurring:
            income.is_recurring = True
            changed = True
        if income.recurrence_type != "monthly":
            income.recurrence_type = "monthly"
            changed = True
        if income.parent_income_id is None:
            income.parent_income_id = income.id
            changed = True
        if income.period_date is None:
            income.period_date = income.income_date
            changed = True
        if changed:
            changed_count += 1
            logger.info(
                "Make income recurring: id=%s title=%s old_is_recurring=%s old_recurrence_type=%s old_parent=%s new_parent=%s period_date=%s",
                income.id,
                income.title,
                old_is_recurring,
                old_recurrence_type,
                old_parent_income_id,
                income.parent_income_id,
                income.period_date,
            )
    if changed_count:
        await session.commit()
    return changed_count


async def normalize_all_existing_incomes_as_recurring(session: AsyncSession, user_id: int | None = None) -> dict:
    incomes = await incomes_repo.list_all(session, user_id)
    changed_count = 0
    for income in incomes:
        old_is_recurring = income.is_recurring
        old_recurrence_type = income.recurrence_type
        old_parent_income_id = income.parent_income_id
        changed = False
        if not income.is_recurring:
            income.is_recurring = True
            changed = True
        if income.recurrence_type != "monthly":
            income.recurrence_type = "monthly"
            changed = True
        if income.period_date is None:
            income.period_date = income.income_date
            changed = True
        if income.parent_income_id is None:
            income.parent_income_id = income.id
            changed = True
        if changed:
            changed_count += 1
            logger.info(
                "Make income recurring: id=%s title=%s old_is_recurring=%s old_recurrence_type=%s old_parent=%s new_parent=%s period_date=%s",
                income.id,
                income.title,
                old_is_recurring,
                old_recurrence_type,
                old_parent_income_id,
                income.parent_income_id,
                income.period_date,
            )
    await session.commit()
    return {"incomes_made_recurring": changed_count}


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
