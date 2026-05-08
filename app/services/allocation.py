from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations import IncomeCalculationDTO, ObligationCalculationDTO, calculate_income_allocation
from app.repositories import incomes as incomes_repo
from app.repositories import obligations as obligations_repo
from app.repositories import payments as payments_repo
from app.repositories import reserves as reserves_repo
from app.services import living_minimum as living_minimum_service
from app.services import savings as savings_service


def _income_dto(income) -> IncomeCalculationDTO:
    return IncomeCalculationDTO(income.id, income.title, income.amount, income.income_date, income.status)


async def _obligation_dto(session: AsyncSession, obligation) -> ObligationCalculationDTO:
    reserved = await reserves_repo.sum_reserved_for_obligation(session, obligation.user_id, obligation.id)
    paid = await payments_repo.sum_paid_for_obligation_period(session, obligation.id, None, obligation.next_payment_date)
    return ObligationCalculationDTO(
        id=obligation.id,
        title=obligation.title,
        type=obligation.type,
        monthly_payment_amount=obligation.monthly_payment_amount,
        next_payment_date=obligation.next_payment_date,
        priority=obligation.priority,
        reserved_amount=reserved,
        paid_amount=paid,
        is_recurring=obligation.is_recurring,
    )


async def process_received_income(session: AsyncSession, user_id: int, income_id: int, today: date):
    income = await incomes_repo.get_by_id(session, user_id, income_id)
    if income is None:
        return None
    obligations = await obligations_repo.list_active_by_user(session, user_id)
    future_incomes = await incomes_repo.list_future_by_user(session, user_id, income.income_date)
    existing_reserves = await reserves_repo.list_by_income(session, income.id)
    existing_by_obligation: dict[int, int] = {}
    income_reserved_total = 0
    income_released_total = 0
    for tx in existing_reserves:
        if tx.transaction_type == "reserve":
            income_reserved_total += tx.amount
        if tx.transaction_type == "release":
            income_released_total += tx.amount
        if tx.obligation_id is not None and tx.transaction_type == "reserve":
            existing_by_obligation[tx.obligation_id] = existing_by_obligation.get(tx.obligation_id, 0) + tx.amount

    obligation_dtos = []
    for obligation in obligations:
        dto = await _obligation_dto(session, obligation)
        # При повторном пересчёте последнего дохода убираем из "уже отложено"
        # резервы, созданные этим же доходом, чтобы показать пользователю ту же
        # рекомендацию, но не создать дубли reserve_transactions.
        dto = ObligationCalculationDTO(
            id=dto.id,
            title=dto.title,
            type=dto.type,
            monthly_payment_amount=dto.monthly_payment_amount,
            next_payment_date=dto.next_payment_date,
            priority=dto.priority,
            reserved_amount=max(0, dto.reserved_amount - existing_by_obligation.get(dto.id, 0)),
            paid_amount=dto.paid_amount,
            is_recurring=dto.is_recurring,
        )
        obligation_dtos.append(dto)
    result = calculate_income_allocation(_income_dto(income), obligation_dtos, [_income_dto(item) for item in future_incomes], today)
    should_create_reserves = income_reserved_total == 0 or income_released_total >= income_reserved_total
    if should_create_reserves:
        txs = [
            {
                "user_id": user_id,
                "obligation_id": item.obligation_id,
                "income_id": income.id,
                "amount": item.recommended_reserve,
                "transaction_type": "reserve",
                "comment": f"Резерв из дохода {income.title}",
            }
            for item in result.items
            if item.recommended_reserve > 0
        ]
        if txs:
            await reserves_repo.bulk_create(session, txs)
    savings = await savings_service.process_savings_for_income(
        session,
        user_id=user_id,
        income_id=income.id,
        income_amount=income.amount,
        available_after_payments=result.safe_to_spend,
    )
    result.savings_enabled = savings["is_enabled"]
    result.savings_percent = savings["percent"]
    result.desired_savings_amount = savings["desired_savings"]
    result.actual_savings_amount = savings["actual_savings"]
    result.safe_to_spend = max(0, result.safe_to_spend - result.actual_savings_amount)
    living = await living_minimum_service.get_living_minimum_settings(session, user_id)
    result.living_minimum_enabled = living.is_enabled
    result.living_minimum_amount = living.amount if living.is_enabled else 0
    result.living_minimum_gap = max(0, result.living_minimum_amount - result.safe_to_spend)
    return result


async def recalculate_last_income(session: AsyncSession, user_id: int, today: date):
    income = await incomes_repo.get_last_received(session, user_id, 60)
    if income is None:
        return None
    return await process_received_income(session, user_id, income.id, today)


async def release_reserves_for_income(session: AsyncSession, user_id: int, income_id: int):
    await reserves_repo.release_by_income(session, user_id, income_id)
    await savings_service.release_savings_for_income(session, user_id, income_id)


async def recalculate_user_plan(session: AsyncSession, user_id: int, today: date):
    result = await recalculate_last_income(session, user_id, today)
    return {"has_received_income": result is not None, "allocation": result}
