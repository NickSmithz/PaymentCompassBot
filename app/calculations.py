from dataclasses import dataclass, field
from datetime import date
from math import ceil


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


def _future_income_sum(
    future_incomes: list[IncomeCalculationDTO], current_income: IncomeCalculationDTO, due_date: date
) -> int:
    return sum(
        income.amount
        for income in future_incomes
        if income.income_date > current_income.income_date
        and income.income_date <= due_date
        and income.status in {"expected", "received"}
    )


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
) -> AllocationResult:
    current_income_remaining = max(0, current_income.amount)
    items: list[AllocationItem] = []
    warnings: list[str] = []

    for obligation in sort_obligations_by_priority(obligations, today):
        remaining_amount = calculate_remaining_amount(obligation)
        if remaining_amount <= 0:
            continue
        future_sum = _future_income_sum(future_incomes, current_income, obligation.next_payment_date)
        total_available_until_due = current_income_remaining + future_sum
        recommended_reserve = 0

        if remaining_amount > 0 and current_income_remaining > 0:
            last_income_before_due = future_sum <= 0
            if last_income_before_due:
                recommended_reserve = min(remaining_amount, current_income_remaining)
            elif total_available_until_due > 0:
                current_share = current_income_remaining / total_available_until_due
                recommended_reserve = min(remaining_amount, current_income_remaining, ceil(remaining_amount * current_share))
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
