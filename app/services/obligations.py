from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import obligations as obligations_repo
from app.repositories import payments as payments_repo
from app.repositories import reserves as reserves_repo


async def create_obligation(session: AsyncSession, user_id: int, data: dict):
    initial_reserved = data.pop("already_reserved_amount", 0)
    obligation = await obligations_repo.create(session, user_id, data)
    if initial_reserved > 0:
        await reserves_repo.create(
            session,
            user_id=user_id,
            obligation_id=obligation.id,
            income_id=None,
            amount=initial_reserved,
            transaction_type="manual_adjustment",
            comment="Начальный резерв при создании платежа",
        )
    return obligation


async def list_active_obligations(session: AsyncSession, user_id: int):
    return await obligations_repo.list_active_by_user(session, user_id)


async def list_obligations(session: AsyncSession, user_id: int):
    return await obligations_repo.list_by_user(session, user_id)


async def get_obligation(session: AsyncSession, user_id: int, obligation_id: int):
    return await obligations_repo.get_by_id(session, user_id, obligation_id)


async def update_obligation(session: AsyncSession, user_id: int, obligation_id: int, data: dict):
    obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
    if obligation is None:
        return None
    return await obligations_repo.update(session, obligation, data)


async def deactivate_obligation(session: AsyncSession, user_id: int, obligation_id: int):
    obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
    if obligation is None:
        return None
    return await obligations_repo.deactivate(session, obligation)


async def get_upcoming_obligations_summary(session: AsyncSession, user_id: int, today: date):
    obligations = await obligations_repo.list_active_by_user(session, user_id)
    items = []
    for obligation in obligations:
        reserved = await reserves_repo.sum_reserved_for_obligation(session, obligation.id)
        paid = await payments_repo.sum_paid_for_obligation_period(session, obligation.id, None, obligation.next_payment_date)
        remaining = max(0, obligation.monthly_payment_amount - reserved - paid)
        items.append(
            {
                "id": obligation.id,
                "title": obligation.title,
                "amount": obligation.monthly_payment_amount,
                "date": obligation.next_payment_date,
                "reserved_amount": reserved,
                "paid_amount": paid,
                "remaining_amount": remaining,
                "days_left": (obligation.next_payment_date - today).days,
            }
        )
    items = sorted(items, key=lambda item: item["date"])
    return {
        "items": items,
        "total_required": sum(item["amount"] for item in items),
        "total_reserved": sum(item["reserved_amount"] for item in items),
        "total_paid": sum(item["paid_amount"] for item in items),
        "total_remaining": sum(item["remaining_amount"] for item in items),
    }


async def update_obligation_field(session: AsyncSession, user_id: int, obligation_id: int, field: str, value):
    field_map = {
        "title": "title",
        "type": "type",
        "amount": "monthly_payment_amount",
        "date": "next_payment_date",
        "debt": "total_debt_amount",
        "priority": "priority",
        "recurring": "is_recurring",
        "status": "is_active",
    }
    if field not in field_map:
        raise ValueError("Unsupported obligation field")
    obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
    if obligation is None:
        return None
    data = {field_map[field]: value}
    if field == "date" and obligation.is_recurring:
        data["payment_day"] = value.day
    if field == "recurring":
        data["payment_day"] = obligation.next_payment_date.day if value else None
    return await obligations_repo.update(session, obligation, data)


async def update_obligation_status(session: AsyncSession, user_id: int, obligation_id: int, is_active: bool):
    return await update_obligation_field(session, user_id, obligation_id, "status", is_active)
