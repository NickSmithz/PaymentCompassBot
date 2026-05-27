import logging
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.calculations import ObligationCalculationDTO, calculate_remaining_amount, calculate_reserved_adjustment
from app.repositories import incomes as incomes_repo
from app.repositories import obligations as obligations_repo
from app.repositories import payments as payments_repo
from app.repositories import reserves as reserves_repo
from app.utils import add_month


logger = logging.getLogger(__name__)


class ReservedAmountValidationError(ValueError):
    def __init__(self, code: str, max_amount: int | None = None):
        super().__init__(code)
        self.code = code
        self.max_amount = max_amount


def generate_obligation_instances(obligations, horizon_start: date, horizon_end: date) -> list[ObligationCalculationDTO]:
    instances: list[ObligationCalculationDTO] = []
    for obligation in obligations:
        due_date = obligation.next_payment_date

        if not obligation.is_recurring:
            if due_date <= horizon_end:
                instances.append(_instance_dto(obligation, due_date))
            continue

        while due_date <= horizon_end:
            if due_date >= horizon_start or due_date == obligation.next_payment_date:
                instances.append(_instance_dto(obligation, due_date))
            due_date = add_month(due_date, obligation.payment_day)

    return instances


def _instance_dto(obligation, due_date: date) -> ObligationCalculationDTO:
    return ObligationCalculationDTO(
        id=obligation.id,
        title=obligation.title,
        type=obligation.type,
        monthly_payment_amount=obligation.monthly_payment_amount,
        next_payment_date=due_date,
        priority=obligation.priority,
        reserved_amount=0,
        paid_amount=0,
        is_recurring=obligation.is_recurring,
        period_date=due_date,
    )


async def generate_relevant_obligation_instances(
    session: AsyncSession,
    user_id: int,
    obligations,
    horizon_start: date,
    horizon_end: date,
) -> list[ObligationCalculationDTO]:
    instances: list[ObligationCalculationDTO] = []
    for obligation in obligations:
        selected = await _first_uncovered_instance(session, user_id, obligation, horizon_start, horizon_end)
        if selected is not None:
            instances.append(selected)
    return instances


async def has_earlier_uncovered_instance(
    session: AsyncSession,
    user_id: int,
    obligation_id: int,
    period_date: date,
) -> bool:
    obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
    if obligation is None or not obligation.is_active:
        return False

    due_date = obligation.next_payment_date
    if due_date >= period_date:
        return False

    while due_date < period_date:
        remaining = await _remaining_for_period(session, user_id, obligation, due_date)
        if remaining > 0:
            logger.debug(
                "Skip future instance: obligation_id=%s title=%s period_date=%s reason=earlier_instance_uncovered",
                obligation.id,
                obligation.title,
                period_date,
            )
            return True
        if not obligation.is_recurring:
            break
        due_date = add_month(due_date, obligation.payment_day)
    return False


async def _first_uncovered_instance(
    session: AsyncSession,
    user_id: int,
    obligation,
    horizon_start: date,
    horizon_end: date,
) -> ObligationCalculationDTO | None:
    due_date = obligation.next_payment_date
    while due_date <= horizon_end:
        reserved = await reserves_repo.sum_reserved_for_obligation_period(session, user_id, obligation.id, due_date)
        paid = await payments_repo.sum_paid_for_obligation_period(session, obligation.id, None, due_date)
        required = obligation.monthly_payment_amount
        remaining = max(0, required - reserved - paid)
        selected = remaining > 0
        logger.debug(
            "Obligation instance check: obligation_id=%s title=%s period_date=%s required=%s reserved=%s paid=%s remaining=%s selected=%s",
            obligation.id,
            obligation.title,
            due_date,
            required,
            reserved,
            paid,
            remaining,
            selected,
        )
        if selected:
            return ObligationCalculationDTO(
                id=obligation.id,
                title=obligation.title,
                type=obligation.type,
                monthly_payment_amount=obligation.monthly_payment_amount,
                next_payment_date=due_date,
                priority=obligation.priority,
                reserved_amount=reserved,
                paid_amount=paid,
                is_recurring=obligation.is_recurring,
                period_date=due_date,
            )
        if not obligation.is_recurring:
            return None
        due_date = add_month(due_date, obligation.payment_day)
    return None


async def _remaining_for_period(session: AsyncSession, user_id: int, obligation, period_date: date) -> int:
    reserved = await reserves_repo.sum_reserved_for_obligation_period(session, user_id, obligation.id, period_date)
    paid = await payments_repo.sum_paid_for_obligation_period(session, obligation.id, None, period_date)
    return max(0, obligation.monthly_payment_amount - reserved - paid)


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
            source="manual",
            period_date=obligation.next_payment_date,
            comment="Начальная сумма «Уже отложено» при создании платежа",
        )
        await session.commit()
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
    horizon_end = today + timedelta(days=get_settings().planning_horizon_days)
    instances = await generate_relevant_obligation_instances(session, user_id, obligations, today, horizon_end)
    items = []
    obligations_by_id = {obligation.id: obligation for obligation in obligations}
    for instance in instances:
        obligation = obligations_by_id.get(instance.id)
        if obligation is None:
            continue
        period_date = instance.period_date or instance.next_payment_date
        paid = instance.paid_amount
        max_allowed_reserved = max(0, instance.monthly_payment_amount - paid)
        reserved = min(instance.reserved_amount, max_allowed_reserved)
        remaining = calculate_remaining_amount(
            ObligationCalculationDTO(
                id=instance.id,
                title=instance.title,
                type=instance.type,
                monthly_payment_amount=instance.monthly_payment_amount,
                next_payment_date=instance.next_payment_date,
                priority=instance.priority,
                reserved_amount=reserved,
                paid_amount=paid,
                is_recurring=instance.is_recurring,
                period_date=period_date,
            )
        )
        future_income_sum_before_due = await incomes_repo.sum_expected_between(
            session,
            user_id,
            today,
            instance.next_payment_date,
        )
        items.append(
            {
                "id": obligation.id,
                "title": obligation.title,
                "amount": obligation.monthly_payment_amount,
                "date": instance.next_payment_date,
                "period_date": period_date,
                "reserved_amount": reserved,
                "paid_amount": paid,
                "remaining_amount": remaining,
                "future_income_sum_before_due": future_income_sum_before_due,
                "has_future_income_before_due": future_income_sum_before_due > 0,
                "days_left": (instance.next_payment_date - today).days,
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


async def get_obligation_reserved_amount_info(session: AsyncSession, user_id: int, obligation_id: int):
    obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
    if obligation is None or not obligation.is_active:
        return None
    current_reserved = await reserves_repo.sum_reserved_for_obligation_period(
        session,
        user_id,
        obligation.id,
        obligation.next_payment_date,
    )
    return {"obligation": obligation, "current_reserved_amount": current_reserved}


async def update_obligation_reserved_amount(
    session: AsyncSession,
    user_id: int,
    obligation_id: int,
    new_reserved_amount: int,
    today: date,
):
    obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
    if obligation is None or not obligation.is_active:
        return None
    if new_reserved_amount < 0:
        raise ReservedAmountValidationError("negative")
    if new_reserved_amount > obligation.monthly_payment_amount:
        raise ReservedAmountValidationError("too_large", max_amount=obligation.monthly_payment_amount)

    period_date = obligation.next_payment_date
    current_reserved = await reserves_repo.sum_reserved_for_obligation_period(
        session,
        user_id,
        obligation.id,
        period_date,
    )
    adjustment = calculate_reserved_adjustment(current_reserved, new_reserved_amount)
    transaction_type = adjustment["transaction_type"]
    amount = adjustment["amount"]
    if transaction_type == "manual_adjustment":
        await reserves_repo.create(
            session,
            user_id=user_id,
            obligation_id=obligation.id,
            income_id=None,
            amount=amount,
            transaction_type="manual_adjustment",
            source="manual",
            period_date=period_date,
            comment="Ручное увеличение суммы «Уже отложено»",
        )
        await session.commit()
    elif transaction_type == "release":
        await reserves_repo.create(
            session,
            user_id=user_id,
            obligation_id=obligation.id,
            income_id=None,
            amount=amount,
            transaction_type="release",
            source="manual",
            period_date=period_date,
            comment="Ручное уменьшение суммы «Уже отложено»",
        )
        await session.commit()

    from app.services import allocation as allocation_service

    recalculation_result = await allocation_service.recalculate_user_plan(session, user_id, today)
    delta = adjustment["delta"]
    if delta > 0:
        message_type = "increased"
    elif delta < 0:
        message_type = "decreased"
    else:
        message_type = "unchanged"
    return {
        "obligation": obligation,
        "old_reserved_amount": current_reserved,
        "new_reserved_amount": new_reserved_amount,
        "delta": delta,
        "recalculation_result": recalculation_result["allocation"] if recalculation_result else None,
        "message_type": message_type,
    }
