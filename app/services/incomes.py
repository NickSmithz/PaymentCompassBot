from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import incomes as incomes_repo
from app.repositories import users as users_repo
from app.services.planning import get_now, get_today


def _now() -> datetime:
    return get_now()


async def create_income(session: AsyncSession, user_id: int, data: dict, now: datetime | None = None):
    payload = dict(data)
    payload.setdefault("period_date", payload.get("income_date"))
    payload.setdefault("is_recurring", False)
    if payload.get("is_recurring"):
        payload["recurrence_type"] = "monthly"
    else:
        payload["recurrence_type"] = None
        payload["parent_income_id"] = None
    if payload.get("status") == "received":
        payload["received_at"] = now or _now()
    else:
        payload["received_at"] = None
    income = await incomes_repo.create(session, user_id, payload)
    if income.is_recurring and income.parent_income_id is None:
        income.parent_income_id = income.id
        if income.period_date is None:
            income.period_date = income.income_date
        await session.commit()
        await session.refresh(income)
    return income


async def create_income_from_user_input(
    session: AsyncSession,
    user_id: int,
    data: dict,
    today: date,
    now: datetime,
) -> dict:
    from app.services import allocation as allocation_service
    from app.services import income_recurrence

    income = await create_income(session, user_id, data, now=now)
    allocation_result = None
    if income.status == "received":
        await income_recurrence.ensure_income_instances(session, user_id, today)
        allocation_result = await allocation_service.process_received_income(session, user_id, income.id, today)
        await users_repo.update_last_focus_income_id(session, user_id, income.id)
        await income_recurrence.create_next_income_instance_if_needed(session, user_id, income.id, today)
    return {"income": income, "allocation": allocation_result}


async def list_incomes(session: AsyncSession, user_id: int):
    return await incomes_repo.list_by_user(session, user_id)


async def list_incomes_for_status_change(session: AsyncSession, user_id: int):
    return await incomes_repo.list_incomes_for_status_change(session, user_id)


async def get_user_incomes_summary(session: AsyncSession, user_id: int, today: date | None = None):
    from app.services import income_recurrence

    today = today or get_today()
    await income_recurrence.ensure_income_instances(session, user_id, today)
    incomes = await incomes_repo.list_by_user(session, user_id)

    def sort_key(income):
        if income.income_date < today:
            return (1, -income.income_date.toordinal(), income.id)
        return (0, income.income_date.toordinal(), income.id)

    sorted_incomes = sorted(incomes, key=sort_key)
    return {
        "incomes": sorted_incomes,
        "total_all": sum(income.amount for income in incomes if income.status != "cancelled"),
        "total_received": sum(income.amount for income in incomes if income.status == "received"),
        "total_expected": sum(income.amount for income in incomes if income.status == "expected"),
        "total_cancelled": sum(income.amount for income in incomes if income.status == "cancelled"),
    }


async def list_future_incomes(session: AsyncSession, user_id: int, from_date: date):
    return await incomes_repo.list_future_by_user(session, user_id, from_date)


async def get_last_received_income(session: AsyncSession, user_id: int, days: int = 60):
    return await incomes_repo.get_last_received(session, user_id, days)


async def update_income(session: AsyncSession, user_id: int, income_id: int, data: dict):
    from app.services import allocation as allocation_service

    income = await incomes_repo.get_by_id(session, user_id, income_id)
    if income is None:
        return None
    if "income_date" in data and "period_date" not in data:
        data["period_date"] = data["income_date"]
    should_reprocess = income.status == "received" and any(key in data for key in {"amount", "income_date"})
    if should_reprocess:
        await allocation_service.release_auto_reserves_for_income(session, user_id, income.id)
    income = await incomes_repo.update(session, income, data)
    if should_reprocess:
        await allocation_service.process_received_income(session, user_id, income.id, get_today())
        await users_repo.update_last_focus_income_id(session, user_id, income.id)
    return income


async def update_income_status(
    session: AsyncSession,
    user_id: int,
    income_id: int,
    new_status: str,
    today: date,
    now: datetime | None = None,
):
    from app.services import allocation as allocation_service
    from app.services import income_recurrence

    if new_status not in {"expected", "received", "cancelled"}:
        raise ValueError("Unsupported income status")
    income = await incomes_repo.get_by_id(session, user_id, income_id)
    if income is None:
        return None
    old_status = income.status
    update_data = {"status": new_status}
    if new_status == "received" and old_status != "received":
        update_data["received_at"] = now or _now()
    elif new_status != "received" and old_status == "received":
        update_data["received_at"] = None
    income = await incomes_repo.update(session, income, update_data)

    allocation_result = None
    recalculation = None
    reserves_released = False
    if new_status == "received" and old_status != "received":
        await income_recurrence.ensure_income_instances(session, user_id, today)
        allocation_result = await allocation_service.process_received_income(session, user_id, income.id, today)
        await users_repo.update_last_focus_income_id(session, user_id, income.id)
        await income_recurrence.create_next_income_instance_if_needed(session, user_id, income.id, today)
    elif old_status == "received" and new_status in {"expected", "cancelled"}:
        await allocation_service.release_reserves_for_income(session, user_id, income.id)
        reserves_released = True
        recalculation = await allocation_service.recalculate_user_plan(session, user_id, today)
    else:
        recalculation = await allocation_service.recalculate_user_plan(session, user_id, today)

    return {
        "income": income,
        "old_status": old_status,
        "new_status": new_status,
        "allocation": allocation_result,
        "recalculation": recalculation,
        "reserves_released": reserves_released,
    }


async def delete_income(session: AsyncSession, user_id: int, income_id: int):
    from app.services import allocation as allocation_service

    income = await incomes_repo.get_by_id(session, user_id, income_id)
    if income is None:
        return False
    if income.status == "received":
        await allocation_service.release_reserves_for_income(session, user_id, income.id)
    await incomes_repo.delete(session, income)
    return True
