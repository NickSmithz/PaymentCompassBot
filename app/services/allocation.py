import logging
from dataclasses import replace
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations import (
    AllocationItem,
    AllocationResult,
    IncomeCalculationDTO,
    ObligationCalculationDTO,
    calculate_income_allocation,
    calculate_overall_risk,
    calculate_remaining_amount,
    calculate_reserve_to_create,
    calculate_safe_to_spend,
)
from app.repositories import incomes as incomes_repo
from app.repositories import obligations as obligations_repo
from app.repositories import payments as payments_repo
from app.repositories import reserves as reserves_repo
from app.services import living_minimum as living_minimum_service
from app.services import savings as savings_service


logger = logging.getLogger(__name__)


def _income_dto(income) -> IncomeCalculationDTO:
    return IncomeCalculationDTO(income.id, income.title, income.amount, income.income_date, income.status)


def _rebuild_result_with_items(result: AllocationResult, items: list[AllocationItem]) -> AllocationResult:
    result.items = items
    result.total_to_reserve = sum(item.recommended_reserve for item in items)
    result.safe_to_spend = calculate_safe_to_spend(result.income_amount, result.total_to_reserve)
    result.overall_risk = calculate_overall_risk(items)
    return result


async def _obligation_dto(session: AsyncSession, obligation) -> ObligationCalculationDTO:
    reserved = await reserves_repo.sum_reserved_for_obligation(session, obligation.user_id, obligation.id)
    paid = await payments_repo.sum_paid_for_obligation_period(session, obligation.id, None, obligation.next_payment_date)
    dto = ObligationCalculationDTO(
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
    logger.debug(
        "Allocation DTO: obligation_id=%s title=%s required=%s reserved=%s paid=%s remaining=%s",
        obligation.id,
        obligation.title,
        obligation.monthly_payment_amount,
        reserved,
        paid,
        calculate_remaining_amount(dto),
    )
    return dto


async def _calculate_received_income(
    session: AsyncSession,
    user_id: int,
    income,
    today: date,
    *,
    exclude_income_reserves: bool,
) -> AllocationResult:
    obligations = await obligations_repo.list_active_by_user(session, user_id)
    future_incomes = await incomes_repo.list_future_by_user(session, user_id, income.income_date)
    existing_by_obligation: dict[int, int] = {}

    if exclude_income_reserves:
        existing_by_obligation = await reserves_repo.auto_reserved_by_obligation_for_income(
            session,
            user_id,
            income.id,
        )

    obligation_dtos = []
    for obligation in obligations:
        dto = await _obligation_dto(session, obligation)
        if exclude_income_reserves:
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

    return calculate_income_allocation(
        _income_dto(income),
        obligation_dtos,
        [_income_dto(item) for item in future_incomes],
        today,
    )


async def _result_from_existing_reserves(
    session: AsyncSession,
    user_id: int,
    income_id: int,
    allocation_result: AllocationResult,
) -> AllocationResult:
    by_obligation = await reserves_repo.auto_reserved_by_obligation_for_income(session, user_id, income_id)
    items = []
    for obligation_id, amount in by_obligation.items():
        obligation = await obligations_repo.get_by_id(session, user_id, obligation_id)
        if obligation is None or amount <= 0:
            continue
        items.append(
            AllocationItem(
                obligation_id=obligation.id,
                title=obligation.title,
                due_date=obligation.next_payment_date,
                required_amount=obligation.monthly_payment_amount,
                remaining_amount=amount,
                recommended_reserve=amount,
                risk="low",
            )
        )
    allocation_result.warnings.append("Резервы по этому доходу уже были созданы ранее.")
    return _rebuild_result_with_items(allocation_result, items)


async def create_reserves_safely(
    session: AsyncSession,
    user_id: int,
    income_id: int,
    allocation_result: AllocationResult,
    today: date,
) -> AllocationResult:
    logger.info("CHECK_EXISTING_RESERVES user_id=%s income_id=%s", user_id, income_id)
    has_existing_reserves = await reserves_repo.has_auto_reserves_for_income(session, user_id, income_id)
    logger.info(
        "HAS_AUTO_RESERVES_FOR_INCOME user_id=%s income_id=%s result=%s",
        user_id,
        income_id,
        has_existing_reserves,
    )
    if has_existing_reserves:
        return await _result_from_existing_reserves(session, user_id, income_id, allocation_result)

    created_items = []
    created_transactions = []
    for item in allocation_result.items:
        if item.recommended_reserve <= 0:
            continue

        obligation = await obligations_repo.get_by_id(session, user_id, item.obligation_id)
        if obligation is None or not obligation.is_active:
            logger.info(
                "Skip reserve: income_id=%s obligation_id=%s title=%s reason=%s",
                income_id,
                item.obligation_id,
                item.title,
                "not found or inactive",
            )
            continue

        current_reserved = await reserves_repo.sum_reserved_for_obligation(session, user_id, obligation.id)
        paid_amount = await payments_repo.sum_paid_for_obligation_period(
            session,
            obligation.id,
            None,
            obligation.next_payment_date,
        )
        current_remaining = calculate_remaining_amount(
            ObligationCalculationDTO(
                id=obligation.id,
                title=obligation.title,
                type=obligation.type,
                monthly_payment_amount=obligation.monthly_payment_amount,
                next_payment_date=obligation.next_payment_date,
                priority=obligation.priority,
                reserved_amount=current_reserved,
                paid_amount=paid_amount,
                is_recurring=obligation.is_recurring,
            )
        )
        amount_to_create = calculate_reserve_to_create(item.recommended_reserve, current_remaining)
        logger.info(
            "RESERVE_ATTEMPT user_id=%s income_id=%s obligation_id=%s title=%s recommended=%s current_reserved=%s paid=%s current_remaining=%s amount_to_create=%s",
            user_id,
            income_id,
            obligation.id,
            obligation.title,
            item.recommended_reserve,
            current_reserved,
            paid_amount,
            current_remaining,
            amount_to_create,
        )
        if amount_to_create <= 0:
            logger.info(
                "Skip reserve: income_id=%s obligation_id=%s title=%s reason=%s",
                income_id,
                obligation.id,
                obligation.title,
                "already covered",
            )
            continue

        tx = await reserves_repo.create(
            session,
            user_id=user_id,
            obligation_id=obligation.id,
            income_id=income_id,
            amount=amount_to_create,
            transaction_type="reserve",
            source="auto_plan",
            comment="Автоматическое резервирование с дохода",
        )
        logger.info(
            "RESERVE_CREATED tx_id=%s user_id=%s income_id=%s obligation_id=%s amount=%s",
            tx.id,
            user_id,
            income_id,
            obligation.id,
            amount_to_create,
        )
        created_transactions.append(tx)
        created_items.append(
            replace(
                item,
                required_amount=obligation.monthly_payment_amount,
                remaining_amount=current_remaining,
                recommended_reserve=amount_to_create,
            )
        )

    if created_transactions:
        await session.commit()
    total_created = sum(item.recommended_reserve for item in created_items)
    logger.info(
        "RESERVES_COMMITTED user_id=%s income_id=%s created_count=%s total_created=%s",
        user_id,
        income_id,
        len(created_items),
        total_created,
    )

    for item in created_items:
        check_reserved = await reserves_repo.sum_reserved_for_obligation(session, user_id, item.obligation_id)
        logger.info(
            "RESERVE_VERIFY obligation_id=%s title=%s sum_reserved_after_commit=%s",
            item.obligation_id,
            item.title,
            check_reserved,
        )

    if allocation_result.total_to_reserve > 0 and not created_items:
        allocation_result.warnings.append("Не удалось сохранить резервы. Попробуй ещё раз или проверь логи.")
    return _rebuild_result_with_items(allocation_result, created_items)


async def _apply_savings_and_living_minimum(
    session: AsyncSession,
    user_id: int,
    income,
    result: AllocationResult,
    *,
    persist_savings: bool,
) -> AllocationResult:
    if persist_savings:
        savings = await savings_service.process_savings_for_income(
            session,
            user_id=user_id,
            income_id=income.id,
            income_amount=income.amount,
            available_after_payments=result.safe_to_spend,
        )
    else:
        savings = await savings_service.preview_savings_for_income(
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
    living = await living_minimum_service.preview_living_minimum_settings(session, user_id)
    result.living_minimum_enabled = living["is_enabled"]
    result.living_minimum_amount = living["amount"] if living["is_enabled"] else 0
    result.living_minimum_gap = max(0, result.living_minimum_amount - result.safe_to_spend)
    return result


async def process_received_income(session: AsyncSession, user_id: int, income_id: int, today: date):
    income = await incomes_repo.get_by_id(session, user_id, income_id)
    if income is None:
        return None
    logger.info(
        "PROCESS_RECEIVED_INCOME_START user_id=%s income_id=%s title=%s amount=%s",
        user_id,
        income.id,
        income.title,
        income.amount,
    )
    result = await _calculate_received_income(session, user_id, income, today, exclude_income_reserves=True)
    result = await create_reserves_safely(session, user_id, income.id, result, today)
    return await _apply_savings_and_living_minimum(session, user_id, income, result, persist_savings=True)


async def recalculate_last_income(session: AsyncSession, user_id: int, today: date):
    income = await incomes_repo.get_last_received(session, user_id, 60)
    if income is None:
        return None
    result = await _calculate_received_income(session, user_id, income, today, exclude_income_reserves=True)
    if await reserves_repo.has_auto_reserves_for_income(session, user_id, income.id):
        result = await _result_from_existing_reserves(session, user_id, income.id, result)
    else:
        result = _rebuild_result_with_items(result, [])
        result.warnings.append(
            "Для этого дохода ещё нет сохранённого расчёта. Измени статус дохода на «Уже пришёл» или добавь доход заново."
        )
    return await _apply_savings_and_living_minimum(session, user_id, income, result, persist_savings=False)


async def release_auto_reserves_for_income(session: AsyncSession, user_id: int, income_id: int):
    releases = await reserves_repo.release_auto_reserves_for_income(session, user_id, income_id)
    for tx in releases:
        logger.info(
            "RELEASE_AUTO_RESERVE income_id=%s obligation_id=%s release_amount=%s",
            income_id,
            tx.obligation_id,
            tx.amount,
        )
    return releases


async def release_reserves_for_income(session: AsyncSession, user_id: int, income_id: int):
    await release_auto_reserves_for_income(session, user_id, income_id)
    await savings_service.release_savings_for_income(session, user_id, income_id)


async def recalculate_user_plan(session: AsyncSession, user_id: int, today: date):
    result = await recalculate_last_income(session, user_id, today)
    return {"has_received_income": result is not None, "allocation": result}
