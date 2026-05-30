import logging
from dataclasses import dataclass, field, replace
from datetime import date

from app.utils import add_month


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncomeCalculationDTO:
    id: int
    title: str
    amount: int
    income_date: date
    status: str


@dataclass(frozen=True)
class ObligationCalculationDTO:
    id: int
    title: str
    type: str
    monthly_payment_amount: int
    next_payment_date: date
    priority: int
    reserved_amount: int
    paid_amount: int
    is_recurring: bool
    period_date: date | None = None


@dataclass
class AllocationItem:
    obligation_id: int
    title: str
    due_date: date
    period_date: date
    required_amount: int
    remaining_amount: int
    recommended_reserve: int
    risk: str


@dataclass
class AllocationResult:
    income_id: int
    income_title: str
    income_amount: int
    total_to_reserve: int
    safe_to_spend: int
    overall_risk: str
    savings_enabled: bool = False
    savings_percent: int | None = None
    desired_savings_amount: int = 0
    actual_savings_amount: int = 0
    living_minimum_enabled: bool = False
    living_minimum_amount: int = 0
    living_minimum_gap: int = 0
    items: list[AllocationItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CashflowGapDTO:
    obligation_id: int
    title: str
    period_date: date
    due_date: date
    gap_amount: int
    reason: str


@dataclass
class PurchaseImpactResult:
    purchase_amount: int
    safe_to_spend_before: int
    safe_to_spend_after: int
    overspend_amount: int
    daily_limit_before: int | None
    daily_limit_after: int | None
    daily_limit_delta: int | None
    living_gap_before: int
    living_gap_after: int
    risk_after: str
    recommendation_type: str
    warnings: list[str] = field(default_factory=list)


def calculate_remaining_amount(obligation: ObligationCalculationDTO) -> int:
    return max(0, obligation.monthly_payment_amount - obligation.reserved_amount - obligation.paid_amount)


ObligationInstanceDTO = ObligationCalculationDTO


def calculate_reserved_balance(transactions) -> int:
    total = 0
    for tx in transactions:
        transaction_type = tx.get("transaction_type") if isinstance(tx, dict) else tx.transaction_type
        amount = tx.get("amount") if isinstance(tx, dict) else tx.amount
        if transaction_type in {"reserve", "manual_adjustment"}:
            total += amount
        elif transaction_type == "release":
            total -= amount
    return max(0, total)


def calculate_safe_to_spend(income_amount: int, total_to_reserve: int) -> int:
    return max(0, income_amount - total_to_reserve)


def normalize_money_for_display(amount: int) -> int:
    return (max(0, amount) // 100) * 100


def distribute_amount_without_rounding_loss(total_amount: int, weights: list[int]) -> list[int]:
    if total_amount <= 0:
        return [0 for _ in weights]

    safe_weights = [max(0, int(weight)) for weight in weights]
    total_weight = sum(safe_weights)
    if total_weight <= 0:
        return [0 for _ in weights]

    rows = []
    for index, weight in enumerate(safe_weights):
        numerator = total_amount * weight
        rows.append(
            {
                "index": index,
                "base": numerator // total_weight,
                "remainder": numerator % total_weight,
            }
        )

    parts = [row["base"] for row in rows]
    leftover = total_amount - sum(parts)
    rows_sorted = sorted(rows, key=lambda row: (-row["remainder"], row["index"]))
    for row in rows_sorted[:leftover]:
        parts[row["index"]] += 1
    return parts


def normalize_allocation_totals(result: AllocationResult) -> AllocationResult:
    income_remaining = max(0, result.income_amount)
    normalized_items: list[AllocationItem] = []
    for item in result.items:
        amount = min(normalize_money_for_display(item.recommended_reserve), income_remaining)
        normalized_items.append(
            AllocationItem(
                obligation_id=item.obligation_id,
                title=item.title,
                due_date=item.due_date,
                period_date=item.period_date,
                required_amount=item.required_amount,
                remaining_amount=item.remaining_amount,
                recommended_reserve=amount,
                risk=item.risk,
            )
        )
        income_remaining -= amount

    result.items = normalized_items
    result.total_to_reserve = sum(item.recommended_reserve for item in normalized_items)
    result.safe_to_spend = calculate_safe_to_spend(result.income_amount, result.total_to_reserve)
    result.overall_risk = calculate_overall_risk(normalized_items)
    return result


def calculate_reserve_to_create(recommended_reserve: int, current_remaining: int) -> int:
    return max(0, min(recommended_reserve, current_remaining))


def calculate_reserved_adjustment(current_reserved: int, new_reserved: int) -> dict:
    delta = new_reserved - current_reserved
    if delta > 0:
        return {"delta": delta, "transaction_type": "manual_adjustment", "amount": delta}
    if delta < 0:
        return {"delta": delta, "transaction_type": "release", "amount": abs(delta)}
    return {"delta": 0, "transaction_type": "none", "amount": 0}


def sort_obligations_by_priority(
    obligations: list[ObligationCalculationDTO], today: date
) -> list[ObligationCalculationDTO]:
    def urgency_bucket(item: ObligationCalculationDTO) -> int:
        remaining = calculate_remaining_amount(item)
        days_left = (item.next_payment_date - today).days
        if item.next_payment_date < today and remaining > 0:
            return 0
        if days_left <= 3 and remaining > 0:
            return 1
        if days_left <= 7 and remaining > 0:
            return 2
        return 3

    return sorted(
        obligations,
        key=lambda item: (
            urgency_bucket(item),
            item.next_payment_date,
            item.priority,
            -item.monthly_payment_amount,
        ),
    )


def _future_incomes_before_due(
    future_incomes: list[IncomeCalculationDTO], current_income: IncomeCalculationDTO, due_date: date
) -> list[IncomeCalculationDTO]:
    return [
        income
        for income in future_incomes
        if income.income_date > current_income.income_date
        and income.income_date <= due_date
        and income.status in {"expected", "received"}
    ]


def _current_income_share_for_obligation(
    remaining_amount: int,
    current_income_remaining: int,
    future_incomes_until_due: list[IncomeCalculationDTO],
) -> int:
    current_weight = normalize_money_for_display(current_income_remaining) // 100
    future_weights = [normalize_money_for_display(income.amount) // 100 for income in future_incomes_until_due]
    weights = [current_weight, *future_weights]
    total_available = sum(weights)
    total_to_distribute = min(normalize_money_for_display(remaining_amount) // 100, total_available)
    return distribute_amount_without_rounding_loss(total_to_distribute, weights)[0] * 100


def _item_key(item: AllocationItem | ObligationCalculationDTO) -> tuple[int, date]:
    if isinstance(item, AllocationItem):
        return (item.obligation_id, item.period_date)
    return (item.id, item.period_date or item.next_payment_date)


def _expected_future_income_sum_until(
    future_incomes: list[IncomeCalculationDTO],
    current_income_date: date,
    due_date: date,
) -> int:
    return sum(
        income.amount
        for income in future_incomes
        if income.status == "expected"
        and income.income_date > current_income_date
        and income.income_date <= due_date
    )


def _allocated_by_obligation_period(current_reserves: list[AllocationItem]) -> dict[tuple[int, date], int]:
    allocated: dict[tuple[int, date], int] = {}
    for item in current_reserves:
        key = _item_key(item)
        allocated[key] = allocated.get(key, 0) + item.recommended_reserve
    return allocated


def _remaining_after_current_allocation(
    instance: ObligationCalculationDTO,
    allocated_by_key: dict[tuple[int, date], int],
) -> int:
    return max(0, calculate_remaining_amount(instance) - allocated_by_key.get(_item_key(instance), 0))


def _expand_cashflow_payment_instances(
    payment_instances: list[ObligationCalculationDTO],
    allocated_by_key: dict[tuple[int, date], int],
    horizon_end: date,
) -> list[ObligationCalculationDTO]:
    expanded: list[ObligationCalculationDTO] = []
    seen: set[tuple[int, date]] = set()

    for instance in payment_instances:
        current = instance
        preferred_day = (instance.period_date or instance.next_payment_date).day

        while current.next_payment_date <= horizon_end:
            key = _item_key(current)
            if key not in seen:
                expanded.append(current)
                seen.add(key)

            if not current.is_recurring or _remaining_after_current_allocation(current, allocated_by_key) > 0:
                break

            next_due = add_month(current.next_payment_date, preferred_day)
            current = replace(
                instance,
                next_payment_date=next_due,
                period_date=next_due,
                reserved_amount=0,
                paid_amount=0,
            )

    return expanded


def calculate_future_cashflow_gaps(
    current_income_id: int,
    current_income_amount: int,
    current_income_date: date,
    payment_instances: list[ObligationCalculationDTO],
    future_incomes: list[IncomeCalculationDTO],
    current_reserves: list[AllocationItem],
    horizon_end: date,
) -> list[CashflowGapDTO]:
    allocated_by_key = _allocated_by_obligation_period(current_reserves)
    payment_instances = _expand_cashflow_payment_instances(payment_instances, allocated_by_key, horizon_end)
    instances = [
        instance
        for instance in payment_instances
        if instance.next_payment_date <= horizon_end
        and _remaining_after_current_allocation(instance, allocated_by_key) > 0
    ]
    instances = sorted(
        instances,
        key=lambda item: (item.next_payment_date, item.priority, item.id),
    )
    gaps: list[CashflowGapDTO] = []
    for due_date in sorted({instance.next_payment_date for instance in instances}):
        required_until_date = sum(
            _remaining_after_current_allocation(instance, allocated_by_key)
            for instance in instances
            if instance.next_payment_date <= due_date
        )
        future_income_until_date = _expected_future_income_sum_until(future_incomes, current_income_date, due_date)
        gap = max(0, required_until_date - future_income_until_date)
        available_from_current_income = max(
            0,
            current_income_amount - sum(item.recommended_reserve for item in current_reserves),
        )
        logger.info(
            "Cashflow gap check: income_id=%s due_date=%s required_until=%s future_income_until=%s gap=%s available_current=%s",
            current_income_id,
            due_date,
            required_until_date,
            future_income_until_date,
            gap,
            available_from_current_income,
        )
        if gap <= 0:
            continue

        target = next(
            (
                instance
                for instance in instances
                if instance.next_payment_date <= due_date
                and _remaining_after_current_allocation(instance, allocated_by_key) > 0
            ),
            None,
        )
        if target is None:
            continue
        gaps.append(
            CashflowGapDTO(
                obligation_id=target.id,
                title=target.title,
                period_date=target.period_date or target.next_payment_date,
                due_date=target.next_payment_date,
                gap_amount=gap,
                reason="Недостаточно будущих доходов до даты платежа",
            )
        )
        break
    return gaps


def _apply_future_cashflow_gap_check(
    current_income: IncomeCalculationDTO,
    obligations: list[ObligationCalculationDTO],
    items: list[AllocationItem],
    future_incomes: list[IncomeCalculationDTO],
    warnings: list[str],
    horizon_end: date,
) -> list[AllocationItem]:
    if not obligations:
        return items

    adjusted_items = list(items)
    item_indexes = {_item_key(item): index for index, item in enumerate(adjusted_items)}
    allocated_before_gap = sum(item.recommended_reserve for item in adjusted_items)
    logger.info(
        "Cashflow check input: income_id=%s income_title=%s income_amount=%s allocated_before_gap=%s safe_before_gap=%s",
        current_income.id,
        current_income.title,
        current_income.amount,
        allocated_before_gap,
        current_income.amount - allocated_before_gap,
    )

    while True:
        allocated_by_key = _allocated_by_obligation_period(adjusted_items)
        cashflow_instances = _expand_cashflow_payment_instances(obligations, allocated_by_key, horizon_end)
        obligations_by_key = {_item_key(obligation): obligation for obligation in cashflow_instances}
        logger.info(
            "Cashflow future incomes: income_id=%s future=%s",
            current_income.id,
            [
                (income.id, income.title, income.income_date, income.amount, income.status)
                for income in future_incomes
            ],
        )
        logger.info(
            "Cashflow payment instances: income_id=%s payments=%s",
            current_income.id,
            [
                (
                    obligation.id,
                    obligation.title,
                    obligation.period_date or obligation.next_payment_date,
                    _remaining_after_current_allocation(obligation, allocated_by_key),
                )
                for obligation in cashflow_instances
            ],
        )
        gaps = calculate_future_cashflow_gaps(
            current_income_id=current_income.id,
            current_income_amount=current_income.amount,
            current_income_date=current_income.income_date,
            payment_instances=obligations,
            future_incomes=future_incomes,
            current_reserves=adjusted_items,
            horizon_end=horizon_end,
        )
        logger.info(
            "Cashflow gaps found: income_id=%s gaps=%s",
            current_income.id,
            [(gap.title, gap.period_date, gap.gap_amount) for gap in gaps],
        )
        if not gaps:
            break

        gap = gaps[0]
        key = (gap.obligation_id, gap.period_date)
        item_index = item_indexes.get(key)
        if item_index is None:
            obligation = obligations_by_key.get(key)
            if obligation is None:
                logger.warning(
                    "Cashflow gap target missing: income_id=%s obligation_id=%s period_date=%s gap=%s",
                    current_income.id,
                    gap.obligation_id,
                    gap.period_date,
                    gap.gap_amount,
                )
                break
            item_index = len(adjusted_items)
            item_indexes[key] = item_index
            adjusted_items.append(
                AllocationItem(
                    obligation_id=obligation.id,
                    title=obligation.title,
                    due_date=obligation.next_payment_date,
                    period_date=obligation.period_date or obligation.next_payment_date,
                    required_amount=obligation.monthly_payment_amount,
                    remaining_amount=calculate_remaining_amount(obligation),
                    recommended_reserve=0,
                    risk="low",
                )
            )

        item = adjusted_items[item_index]
        available_from_current_income = max(
            0,
            current_income.amount - sum(existing.recommended_reserve for existing in adjusted_items),
        )
        current_remaining_for_payment = max(0, item.remaining_amount - item.recommended_reserve)
        extra_reserve = min(gap.gap_amount, available_from_current_income, current_remaining_for_payment)
        logger.info(
            "Apply cashflow gap: income_id=%s obligation_id=%s period_date=%s gap=%s available_current=%s applied=%s",
            current_income.id,
            gap.obligation_id,
            gap.period_date,
            gap.gap_amount,
            available_from_current_income,
            extra_reserve,
        )

        if extra_reserve <= 0:
            adjusted_items[item_index] = replace(item, risk="high")
            warnings.append(
                f"До платежа «{gap.title}» может не хватить {(extra_reserve or gap.gap_amount) // 100} ₽. "
                f"До {gap.due_date.strftime('%d.%m.%Y')} ожидаемых доходов не хватает."
            )
            logger.warning(
                "Cashflow gap not covered: income_id=%s obligation_id=%s period_date=%s gap=%s available_current=%s",
                current_income.id,
                gap.obligation_id,
                gap.period_date,
                gap.gap_amount,
                available_from_current_income,
            )
            break

        adjusted_items[item_index] = replace(
            item,
            recommended_reserve=item.recommended_reserve + extra_reserve,
            risk="medium" if item.risk == "low" else item.risk,
        )
        warnings.append(
            f"Я заранее отложил {extra_reserve // 100} ₽, потому что до платежа "
            f"«{gap.title}» будущих доходов не хватило бы."
        )
        logger.info(
            "Cashflow gap covered: income_id=%s obligation_id=%s period_date=%s amount=%s",
            current_income.id,
            gap.obligation_id,
            gap.period_date,
            extra_reserve,
        )

    allocated_after_gap = sum(item.recommended_reserve for item in adjusted_items)
    logger.info(
        "Cashflow check result: income_id=%s allocated_after_gap=%s safe_after_gap=%s items=%s",
        current_income.id,
        allocated_after_gap,
        current_income.amount - allocated_after_gap,
        [(item.title, item.period_date, item.recommended_reserve) for item in adjusted_items],
    )
    return adjusted_items


def calculate_obligation_risk(
    obligation: ObligationCalculationDTO,
    remaining_amount: int,
    available_until_due: int,
    uses_future_income: bool,
    today: date,
) -> str:
    days_left = (obligation.next_payment_date - today).days
    if obligation.next_payment_date < today and remaining_amount > 0:
        return "high"
    if days_left <= 3 and remaining_amount > available_until_due:
        return "high"
    if days_left <= 7 and remaining_amount > 0:
        return "medium"
    if uses_future_income and remaining_amount > 0:
        return "medium"
    return "low"


def calculate_overall_risk(items: list[AllocationItem]) -> str:
    risks = {item.risk for item in items}
    if "high" in risks:
        return "high"
    if "medium" in risks:
        return "medium"
    return "low"


def calculate_income_allocation(
    current_income: IncomeCalculationDTO,
    obligations: list[ObligationCalculationDTO],
    future_incomes: list[IncomeCalculationDTO],
    today: date,
    horizon_end: date | None = None,
) -> AllocationResult:
    if horizon_end is None and obligations:
        horizon_end = max(obligation.next_payment_date for obligation in obligations)

    current_income_remaining = max(0, current_income.amount)
    items: list[AllocationItem] = []
    warnings: list[str] = []

    for obligation in sort_obligations_by_priority(obligations, today):
        if horizon_end is not None and obligation.next_payment_date > horizon_end:
            continue
        remaining_amount = calculate_remaining_amount(obligation)
        if remaining_amount <= 0:
            continue
        future_incomes_until_due = _future_incomes_before_due(future_incomes, current_income, obligation.next_payment_date)
        future_sum = sum(income.amount for income in future_incomes_until_due)
        total_available_until_due = current_income_remaining + future_sum
        recommended_reserve = 0

        if remaining_amount > 0 and current_income_remaining > 0:
            last_income_before_due = future_sum <= 0
            if last_income_before_due:
                recommended_reserve = min(remaining_amount, current_income_remaining)
            elif total_available_until_due > 0:
                recommended_reserve = _current_income_share_for_obligation(
                    remaining_amount,
                    current_income_remaining,
                    future_incomes_until_due,
                )
                recommended_reserve = min(remaining_amount, current_income_remaining, recommended_reserve)
            recommended_reserve = normalize_money_for_display(recommended_reserve)

        remaining_after_recommendation = max(0, remaining_amount - recommended_reserve)
        uses_future_income = remaining_amount > recommended_reserve and future_sum > 0
        risk = calculate_obligation_risk(
            obligation=obligation,
            remaining_amount=remaining_after_recommendation,
            available_until_due=total_available_until_due,
            uses_future_income=uses_future_income,
            today=today,
        )
        if remaining_after_recommendation > 0 and future_sum <= 0:
            warnings.append(
                f"До платежа «{obligation.title}» может не хватить денег: "
                f"до {obligation.next_payment_date.strftime('%d.%m.%Y')} больше нет ожидаемых доходов."
            )
        elif remaining_amount > total_available_until_due:
            warnings.append(f"До платежа «{obligation.title}» может не хватить денег.")

        items.append(
            AllocationItem(
                obligation_id=obligation.id,
                title=obligation.title,
                due_date=obligation.next_payment_date,
                period_date=obligation.period_date or obligation.next_payment_date,
                required_amount=obligation.monthly_payment_amount,
                remaining_amount=remaining_amount,
                recommended_reserve=recommended_reserve,
                risk=risk,
            )
        )
        current_income_remaining -= recommended_reserve

    items = _apply_future_cashflow_gap_check(
        current_income=current_income,
        obligations=obligations,
        items=items,
        future_incomes=future_incomes,
        warnings=warnings,
        horizon_end=horizon_end or today,
    )

    result = AllocationResult(
        income_id=current_income.id,
        income_title=current_income.title,
        income_amount=current_income.amount,
        total_to_reserve=0,
        safe_to_spend=0,
        overall_risk=calculate_overall_risk(items),
        items=items,
        warnings=warnings,
    )
    return normalize_allocation_totals(result)


def calculate_purchase_impact(
    purchase_amount: int,
    safe_to_spend: int,
    days_until_next_income: int | None,
    living_minimum_enabled: bool,
    living_minimum_amount: int,
    overall_risk: str,
) -> PurchaseImpactResult:
    safe_to_spend_before = max(0, safe_to_spend)
    safe_to_spend_after = max(0, safe_to_spend_before - purchase_amount)
    overspend_amount = max(0, purchase_amount - safe_to_spend_before)

    if days_until_next_income is None:
        daily_limit_before = None
        daily_limit_after = None
        daily_limit_delta = None
    else:
        days = max(1, days_until_next_income)
        daily_limit_before = safe_to_spend_before // days
        daily_limit_after = safe_to_spend_after // days
        daily_limit_delta = daily_limit_before - daily_limit_after

    living_gap_before = max(0, living_minimum_amount - safe_to_spend_before) if living_minimum_enabled else 0
    living_gap_after = max(0, living_minimum_amount - safe_to_spend_after) if living_minimum_enabled else 0
    warnings: list[str] = []
    if days_until_next_income is None:
        warnings.append("Следующий доход не указан, дневной лимит посчитать нельзя.")
    if overspend_amount > 0:
        warnings.append("Покупка больше свободной суммы.")
    if living_minimum_enabled and living_gap_after > 0:
        warnings.append("После покупки свободных денег меньше минимума на жизнь.")
    if overall_risk == "high":
        warnings.append("Риск просрочки уже высокий до покупки.")

    if overall_risk == "high" or overspend_amount > 0 or (safe_to_spend_after == 0 and (days_until_next_income or 0) > 1):
        risk_after = "high"
    elif (
        overall_risk == "medium"
        or (living_minimum_enabled and safe_to_spend_after < living_minimum_amount)
        or (safe_to_spend_before > 0 and safe_to_spend_after < safe_to_spend_before * 0.2)
    ):
        risk_after = "medium"
    else:
        risk_after = "low"

    if (
        purchase_amount <= safe_to_spend_before
        and (not living_minimum_enabled or safe_to_spend_after >= living_minimum_amount)
        and risk_after == "low"
    ):
        recommendation_type = "can_buy"
    elif overspend_amount > 0 or risk_after == "high" or daily_limit_after == 0:
        recommendation_type = "better_not"
    else:
        recommendation_type = "be_careful"

    return PurchaseImpactResult(
        purchase_amount=purchase_amount,
        safe_to_spend_before=safe_to_spend_before,
        safe_to_spend_after=safe_to_spend_after,
        overspend_amount=overspend_amount,
        daily_limit_before=daily_limit_before,
        daily_limit_after=daily_limit_after,
        daily_limit_delta=daily_limit_delta,
        living_gap_before=living_gap_before,
        living_gap_after=living_gap_after,
        risk_after=risk_after,
        recommendation_type=recommendation_type,
        warnings=warnings,
    )
