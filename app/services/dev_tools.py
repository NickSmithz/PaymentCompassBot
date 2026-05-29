from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import incomes as incomes_repo
from app.repositories import living_minimum as living_minimum_repo
from app.repositories import obligations as obligations_repo
from app.repositories import notifications as notifications_repo
from app.repositories import payments as payments_repo
from app.repositories import reserves as reserves_repo
from app.repositories import savings as savings_repo
from app.repositories import users as users_repo
from app.services import income_recurrence


async def reset_user_state_for_testing(session: AsyncSession, user_id: int) -> dict:
    incomes_reset = await incomes_repo.reset_statuses_for_user(session, user_id, "expected")
    obligations_activated = await obligations_repo.activate_all_by_user(session, user_id)
    payment_records_deleted = await payments_repo.delete_by_user(session, user_id)
    reserve_transactions_deleted = await reserves_repo.delete_by_user(session, user_id)

    user = await users_repo.get_by_id(session, user_id)
    last_focus_income_cleared = bool(user and user.last_focus_income_id is not None)
    if user is not None:
        user.last_focus_income_id = None
        user.last_return_prompt_at = None

    await session.commit()
    return {
        "incomes_reset": incomes_reset,
        "obligations_activated": obligations_activated,
        "payment_records_deleted": payment_records_deleted,
        "reserve_transactions_deleted": reserve_transactions_deleted,
        "last_focus_income_cleared": last_focus_income_cleared,
    }


async def clear_user_data_for_testing(session: AsyncSession, user_id: int) -> dict:
    reserve_transactions_deleted = await reserves_repo.delete_by_user(session, user_id)
    payment_records_deleted = await payments_repo.delete_by_user(session, user_id)
    savings_transactions_deleted = await savings_repo.delete_transactions_by_user(session, user_id)
    savings_settings_deleted = await savings_repo.delete_settings_by_user(session, user_id)
    living_settings_deleted = await living_minimum_repo.delete_settings_by_user(session, user_id)
    notification_logs_deleted = await notifications_repo.delete_by_user(session, user_id)
    incomes_deleted = await incomes_repo.delete_by_user(session, user_id)
    obligations_deleted = await obligations_repo.delete_by_user(session, user_id)

    user = await users_repo.get_by_id(session, user_id)
    if user is not None:
        user.last_focus_income_id = None
        user.last_return_prompt_at = None

    await session.commit()
    return {
        "incomes_deleted": incomes_deleted,
        "obligations_deleted": obligations_deleted,
        "payment_records_deleted": payment_records_deleted,
        "reserve_transactions_deleted": reserve_transactions_deleted,
        "savings_transactions_deleted": savings_transactions_deleted,
        "notification_logs_deleted": notification_logs_deleted,
        "settings_deleted": savings_settings_deleted + living_settings_deleted,
    }


async def make_all_incomes_recurring_for_testing(session: AsyncSession, user_id: int, today) -> dict:
    summary = await income_recurrence.normalize_all_existing_incomes_as_recurring(session, user_id)
    created = await income_recurrence.ensure_income_instances(session, user_id, today)
    return {
        "incomes_made_recurring": summary["incomes_made_recurring"],
        "future_instances_created": len(created),
    }
