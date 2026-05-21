from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import incomes as incomes_repo


async def create_income(session: AsyncSession, user_id: int, data: dict):
    return await incomes_repo.create(session, user_id, data)


async def list_incomes(session: AsyncSession, user_id: int):
    return await incomes_repo.list_by_user(session, user_id)


async def get_user_incomes_summary(session: AsyncSession, user_id: int, today: date | None = None):
    incomes = await incomes_repo.list_by_user(session, user_id)
    today = today or date.today()

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
    should_reprocess = income.status == "received" and any(key in data for key in {"amount", "income_date"})
    if should_reprocess:
        await allocation_service.release_auto_reserves_for_income(session, user_id, income.id)
    income = await incomes_repo.update(session, income, data)
    if should_reprocess:
        await allocation_service.process_received_income(session, user_id, income.id, date.today())
    return income


async def update_income_status(session: AsyncSession, user_id: int, income_id: int, new_status: str, today: date):
    from app.services import allocation as allocation_service

    if new_status not in {"expected", "received", "cancelled"}:
        raise ValueError("Unsupported income status")
    income = await incomes_repo.get_by_id(session, user_id, income_id)
    if income is None:
        return None
    old_status = income.status
    income = await incomes_repo.update(session, income, {"status": new_status})

    allocation_result = None
    recalculation = None
    reserves_released = False
    if new_status == "received":
        allocation_result = await allocation_service.process_received_income(session, user_id, income.id, today)
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
