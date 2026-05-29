import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.calculations import AllocationItem, AllocationResult
from app.models import Base, Income, Obligation, PaymentRecord, ReserveTransaction, User
from app.repositories import reserves as reserves_repo
from app.services import allocation as allocation_service
from app.services import obligations as obligation_service
from app.services import payments as payment_service


def run(coro):
    return asyncio.run(coro)


async def make_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def create_user(session, telegram_id: int = 1001) -> User:
    user = User(telegram_id=telegram_id, username="test", first_name="Test")
    session.add(user)
    await session.flush()
    return user


async def create_obligation(session, user_id: int, amount: int, due: date, title: str = "Платёж") -> Obligation:
    obligation = Obligation(
        user_id=user_id,
        title=title,
        type="credit",
        monthly_payment_amount=amount,
        next_payment_date=due,
        payment_day=due.day,
        priority=3,
        is_active=True,
        is_recurring=True,
    )
    session.add(obligation)
    await session.flush()
    return obligation


async def create_income(session, user_id: int, amount: int, day: date, title: str = "Доход") -> Income:
    income = Income(user_id=user_id, title=title, amount=amount, income_date=day, status="received")
    session.add(income)
    await session.flush()
    return income


async def create_expected_income(session, user_id: int, amount: int, day: date, title: str = "Income") -> Income:
    income = Income(user_id=user_id, title=title, amount=amount, income_date=day, status="expected")
    session.add(income)
    await session.flush()
    return income


async def reserve_count(session) -> int:
    return await session.scalar(select(func.count(ReserveTransaction.id))) or 0


def test_process_received_income_creates_readable_auto_reserves():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date.today()
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, 5600 * 100, today + timedelta(days=5), "Манимэн")
                income = await create_income(session, user.id, 30000 * 100, today, "Юнона")
                obligation.is_recurring = False
                await session.commit()

                await allocation_service.process_received_income(session, user.id, income.id, today)

                reserved = await reserves_repo.sum_reserved_for_obligation(session, user.id, obligation.id)
                assert reserved == 5600 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_second_income_does_not_over_reserve_closed_obligation():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date.today()
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, 5600 * 100, today + timedelta(days=5), "Манимэн")
                first_income = await create_income(session, user.id, 30000 * 100, today, "Юнона")
                obligation.is_recurring = False
                await session.commit()
                await allocation_service.process_received_income(session, user.id, first_income.id, today)

                second_income = await create_income(session, user.id, 25000 * 100, today + timedelta(days=1), "Аксенова")
                await session.commit()
                result = await allocation_service.process_received_income(session, user.id, second_income.id, today)

                reserved = await reserves_repo.sum_reserved_for_obligation(session, user.id, obligation.id)
                assert reserved == 5600 * 100
                assert all(item.obligation_id != obligation.id for item in result.items)
        finally:
            await engine.dispose()

    run(scenario())


def test_second_income_reserves_only_remaining_amount():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date.today()
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, 1500 * 100, today + timedelta(days=5), "Кредитка")
                first_income = await create_income(session, user.id, 10000 * 100, today, "Первый доход")
                second_income = await create_income(session, user.id, 25000 * 100, today + timedelta(days=1), "Второй доход")
                obligation.is_recurring = False
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=first_income.id,
                    amount=740 * 100,
                    transaction_type="reserve",
                    source="auto_plan",
                    period_date=obligation.next_payment_date,
                    comment="Автоматическое резервирование с дохода",
                )
                await session.commit()

                result = await allocation_service.process_received_income(session, user.id, second_income.id, today)

                reserved = await reserves_repo.sum_reserved_for_obligation(session, user.id, obligation.id)
                assert reserved <= 1500 * 100
                new_amount = sum(item.recommended_reserve for item in result.items if item.obligation_id == obligation.id)
                assert new_amount <= 760 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_recalculate_last_income_does_not_create_reserve_transactions():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date.today()
            async with Session() as session:
                user = await create_user(session)
                await create_obligation(session, user.id, 5600 * 100, today + timedelta(days=5), "Манимэн")
                await create_income(session, user.id, 30000 * 100, today, "Юнона")
                await session.commit()

                before = await reserve_count(session)
                await allocation_service.recalculate_last_income(session, user.id, today)
                await allocation_service.recalculate_last_income(session, user.id, today)
                after = await reserve_count(session)

                assert before == after == 0
        finally:
            await engine.dispose()

    run(scenario())


def test_has_auto_reserves_false_without_obligation_id():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date.today()
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id, 30000 * 100, today, "Юнона")
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=None,
                    income_id=income.id,
                    amount=1000 * 100,
                    transaction_type="reserve",
                    source="auto_plan",
                    comment="Автоматическое резервирование с дохода",
                )
                await session.commit()

                assert not await reserves_repo.has_auto_reserves_for_income(session, user.id, income.id)
        finally:
            await engine.dispose()

    run(scenario())


def test_release_auto_reserves_for_income_cancels_income_plan():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date.today()
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, 5600 * 100, today + timedelta(days=5), "Манимэн")
                income = await create_income(session, user.id, 30000 * 100, today, "Юнона")
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=income.id,
                    amount=5600 * 100,
                    transaction_type="reserve",
                    source="auto_plan",
                    period_date=obligation.next_payment_date,
                    comment="Автоматическое резервирование с дохода",
                )
                await session.commit()

                await allocation_service.release_auto_reserves_for_income(session, user.id, income.id)

                reserved = await reserves_repo.sum_reserved_for_obligation(session, user.id, obligation.id)
                assert reserved == 0
        finally:
            await engine.dispose()

    run(scenario())


def test_recurring_obligation_generates_future_instances_within_horizon():
    today = date(2026, 5, 28)
    obligation = Obligation(
        id=1,
        user_id=1,
        title="Alpha Credit",
        type="credit",
        monthly_payment_amount=40000 * 100,
        next_payment_date=date(2026, 5, 30),
        payment_day=30,
        priority=3,
        is_active=True,
        is_recurring=True,
    )

    instances = obligation_service.generate_obligation_instances(
        [obligation],
        today,
        today + timedelta(days=45),
    )

    assert [item.period_date for item in instances] == [date(2026, 5, 30), date(2026, 6, 30)]


def test_non_recurring_obligation_does_not_generate_future_instances():
    today = date(2026, 5, 28)
    obligation = Obligation(
        id=1,
        user_id=1,
        title="One Time",
        type="other",
        monthly_payment_amount=10000 * 100,
        next_payment_date=date(2026, 5, 30),
        payment_day=None,
        priority=3,
        is_active=True,
        is_recurring=False,
    )

    instances = obligation_service.generate_obligation_instances(
        [obligation],
        today,
        today + timedelta(days=90),
    )

    assert [item.period_date for item in instances] == [date(2026, 5, 30)]


def test_reserves_are_separated_by_obligation_period():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    40000 * 100,
                    date(2026, 5, 30),
                    "Alpha Credit",
                )
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=None,
                    amount=40000 * 100,
                    transaction_type="reserve",
                    source="auto_plan",
                    period_date=date(2026, 5, 30),
                )
                await session.commit()

                may_reserved = await reserves_repo.sum_reserved_for_obligation_period(
                    session,
                    user.id,
                    obligation.id,
                    date(2026, 5, 30),
                )
                june_reserved = await reserves_repo.sum_reserved_for_obligation_period(
                    session,
                    user.id,
                    obligation.id,
                    date(2026, 6, 30),
                )

                assert may_reserved == 40000 * 100
                assert june_reserved == 0
        finally:
            await engine.dispose()

    run(scenario())


def test_closed_current_recurring_instance_does_not_block_next_instance_allocation():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    40000 * 100,
                    date(2026, 5, 30),
                    "Alpha Credit",
                )
                income = await create_income(session, user.id, 30000 * 100, date(2026, 6, 20), "June Income")
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=None,
                    amount=40000 * 100,
                    transaction_type="manual_adjustment",
                    source="manual",
                    period_date=date(2026, 5, 30),
                )
                await session.commit()

                result = await allocation_service.process_received_income(session, user.id, income.id, today)

                june_items = [
                    item
                    for item in result.items
                    if item.obligation_id == obligation.id and item.period_date == date(2026, 6, 30)
                ]
                assert june_items
                assert june_items[0].recommended_reserve > 0
        finally:
            await engine.dispose()

    run(scenario())


def test_upcoming_obligations_shows_next_open_recurring_instance_when_current_is_closed():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    40000 * 100,
                    date(2026, 5, 30),
                    "Alpha Credit",
                )
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=None,
                    amount=40000 * 100,
                    transaction_type="manual_adjustment",
                    source="manual",
                    period_date=date(2026, 5, 30),
                )
                await session.commit()

                summary = await obligation_service.get_upcoming_obligations_summary(session, user.id, today)

                assert summary["items"][0]["id"] == obligation.id
                assert summary["items"][0]["date"] == date(2026, 6, 30)
                assert summary["items"][0]["remaining_amount"] == 40000 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_allocation_and_upcoming_use_same_future_recurring_instance_source():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 29)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    16000 * 100,
                    date(2026, 6, 15),
                    "Credit Sber",
                )
                income = await create_income(session, user.id, 1000 * 100, date(2026, 7, 1), "Noshchenko")
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=None,
                    amount=16000 * 100,
                    transaction_type="manual_adjustment",
                    source="manual",
                    period_date=date(2026, 6, 15),
                )
                await session.commit()

                allocation = await allocation_service.process_received_income(session, user.id, income.id, today)
                upcoming = await obligation_service.get_upcoming_obligations_summary(session, user.id, today)

                assert [item.due_date for item in allocation.items] == [date(2026, 7, 15)]
                assert [item["date"] for item in upcoming["items"]] == [date(2026, 7, 15)]
                assert upcoming["items"][0]["reserved_amount"] == 1000 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_upcoming_summary_reports_existing_obligations_when_horizon_has_no_instances():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 29)
            async with Session() as session:
                user = await create_user(session)
                await create_obligation(session, user.id, 16000 * 100, date(2026, 12, 15), "Future Credit")
                await session.commit()

                summary = await obligation_service.get_upcoming_obligations_summary(session, user.id, today)

                assert summary["items"] == []
                assert summary["obligations_count"] == 1
                assert summary["active_obligations_count"] == 1
        finally:
            await engine.dispose()

    run(scenario())


def test_recurring_obligation_stays_active_after_full_payment():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, 16000 * 100, date(2026, 6, 15), "Credit Sber")
                await session.commit()

                await payment_service.process_obligation_payment(session, user.id, obligation.id, 16000 * 100, date(2026, 6, 15))
                await session.refresh(obligation)

                assert obligation.is_active is True
                assert obligation.next_payment_date == date(2026, 7, 15)
        finally:
            await engine.dispose()

    run(scenario())


def test_non_recurring_obligation_deactivates_after_full_payment():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, 16000 * 100, date(2026, 6, 15), "One Time")
                obligation.is_recurring = False
                obligation.payment_day = None
                await session.commit()

                await payment_service.process_obligation_payment(session, user.id, obligation.id, 16000 * 100, date(2026, 6, 15))
                await session.refresh(obligation)

                assert obligation.is_active is False
                assert obligation.next_payment_date == date(2026, 6, 15)
        finally:
            await engine.dispose()

    run(scenario())


def test_relevant_instances_returns_current_when_current_is_partially_open():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    40000 * 100,
                    date(2026, 5, 30),
                    "Alpha Credit",
                )
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=None,
                    amount=20000 * 100,
                    transaction_type="manual_adjustment",
                    source="manual",
                    period_date=date(2026, 5, 30),
                )
                await session.commit()

                instances = await obligation_service.generate_relevant_obligation_instances(
                    session,
                    user.id,
                    [obligation],
                    today,
                    today + timedelta(days=45),
                )

                assert [item.period_date for item in instances] == [date(2026, 5, 30)]
        finally:
            await engine.dispose()

    run(scenario())


def test_relevant_instances_returns_next_when_current_is_closed_by_reserve():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    40000 * 100,
                    date(2026, 5, 30),
                    "Alpha Credit",
                )
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=None,
                    amount=40000 * 100,
                    transaction_type="manual_adjustment",
                    source="manual",
                    period_date=date(2026, 5, 30),
                )
                await session.commit()

                instances = await obligation_service.generate_relevant_obligation_instances(
                    session,
                    user.id,
                    [obligation],
                    today,
                    today + timedelta(days=45),
                )

                assert [item.period_date for item in instances] == [date(2026, 6, 30)]
        finally:
            await engine.dispose()

    run(scenario())


def test_relevant_instances_returns_next_when_current_is_closed_by_payment():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    40000 * 100,
                    date(2026, 5, 30),
                    "Alpha Credit",
                )
                session.add(
                    PaymentRecord(
                        user_id=user.id,
                        obligation_id=obligation.id,
                        amount=40000 * 100,
                        paid_at=date(2026, 5, 30),
                        period_date=date(2026, 5, 30),
                    )
                )
                await session.commit()

                instances = await obligation_service.generate_relevant_obligation_instances(
                    session,
                    user.id,
                    [obligation],
                    today,
                    today + timedelta(days=45),
                )

                assert [item.period_date for item in instances] == [date(2026, 6, 30)]
        finally:
            await engine.dispose()

    run(scenario())


def test_create_reserves_safely_skips_future_period_when_earlier_instance_is_open():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    40000 * 100,
                    date(2026, 5, 30),
                    "Alpha Credit",
                )
                income = await create_income(session, user.id, 40000 * 100, today, "Income")
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=None,
                    amount=20000 * 100,
                    transaction_type="manual_adjustment",
                    source="manual",
                    period_date=date(2026, 5, 30),
                )
                await session.commit()

                allocation_result = AllocationResult(
                    income_id=income.id,
                    income_title=income.title,
                    income_amount=income.amount,
                    total_to_reserve=10000 * 100,
                    safe_to_spend=30000 * 100,
                    overall_risk="low",
                    items=[
                        AllocationItem(
                            obligation_id=obligation.id,
                            title=obligation.title,
                            due_date=date(2026, 6, 30),
                            period_date=date(2026, 6, 30),
                            required_amount=obligation.monthly_payment_amount,
                            remaining_amount=40000 * 100,
                            recommended_reserve=10000 * 100,
                            risk="low",
                        )
                    ],
                )

                before = await reserve_count(session)
                result = await allocation_service.create_reserves_safely(
                    session,
                    user.id,
                    income.id,
                    allocation_result,
                    today,
                )
                after = await reserve_count(session)

                assert after == before
                assert result.items == []
        finally:
            await engine.dispose()

    run(scenario())


def test_process_received_income_tops_up_existing_reserve_after_cashflow_gap():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 6, 25)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    641 * 100,
                    date(2026, 7, 5),
                    "Credit Card",
                )
                obligation.is_recurring = False
                income = await create_income(session, user.id, 120000 * 100, today, "Salary")
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=income.id,
                    amount=25 * 100,
                    transaction_type="reserve",
                    source="auto_plan",
                    period_date=obligation.next_payment_date,
                )
                await session.commit()

                allocation_result = AllocationResult(
                    income_id=income.id,
                    income_title=income.title,
                    income_amount=income.amount,
                    total_to_reserve=641 * 100,
                    safe_to_spend=119359 * 100,
                    overall_risk="medium",
                    items=[
                        AllocationItem(
                            obligation_id=obligation.id,
                            title=obligation.title,
                            due_date=obligation.next_payment_date,
                            period_date=obligation.next_payment_date,
                            required_amount=obligation.monthly_payment_amount,
                            remaining_amount=641 * 100,
                            recommended_reserve=641 * 100,
                            risk="medium",
                        )
                    ],
                )

                with patch(
                    "app.services.allocation._calculate_received_income",
                    new=AsyncMock(return_value=allocation_result),
                ):
                    result = await allocation_service.process_received_income(session, user.id, income.id, today)

                reserved = await reserves_repo.sum_reserved_for_obligation_period(
                    session,
                    user.id,
                    obligation.id,
                    obligation.next_payment_date,
                )
                assert reserved == 641 * 100
                assert result.total_to_reserve == 641 * 100
                assert result.safe_to_spend == 119359 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_process_received_income_applies_cashflow_gap_for_next_recurring_period():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 6, 25)
            async with Session() as session:
                user = await create_user(session)
                credit_card = await create_obligation(
                    session,
                    user.id,
                    3000 * 100,
                    date(2026, 6, 5),
                    "Credit Card",
                )
                car_loan = await create_obligation(
                    session,
                    user.id,
                    25000 * 100,
                    date(2026, 6, 10),
                    "Car Loan",
                )
                await create_obligation(session, user.id, 50000 * 100, date(2026, 6, 15), "Mortgage")
                await create_obligation(session, user.id, 30000 * 100, date(2026, 6, 25), "Repair Loan")
                salary = await create_income(session, user.id, 175000 * 100, today, "Salary")
                await create_expected_income(session, user.id, 25000 * 100, date(2026, 7, 5), "Advance")
                await create_expected_income(session, user.id, 175000 * 100, date(2026, 7, 15), "Next Salary")

                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=credit_card.id,
                    income_id=None,
                    amount=3000 * 100,
                    transaction_type="reserve",
                    source="auto_plan",
                    period_date=date(2026, 6, 5),
                )
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=car_loan.id,
                    income_id=None,
                    amount=22000 * 100,
                    transaction_type="reserve",
                    source="auto_plan",
                    period_date=date(2026, 6, 10),
                )
                await session.commit()

                result = await allocation_service.process_received_income(session, user.id, salary.id, today)

                credit_card_july_reserved = await reserves_repo.sum_reserved_for_obligation_period(
                    session,
                    user.id,
                    credit_card.id,
                    date(2026, 7, 5),
                )
                salary_reserved = await reserves_repo.auto_reserved_by_obligation_period_for_income(
                    session,
                    user.id,
                    salary.id,
                )

                assert credit_card_july_reserved == 3000 * 100
                assert sum(salary_reserved.values()) == 86000 * 100
                assert result.total_to_reserve == 86000 * 100
                assert result.safe_to_spend == 89000 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_allocation_does_not_include_duplicate_obligation_when_current_is_open():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    40000 * 100,
                    date(2026, 5, 30),
                    "Alpha Credit",
                )
                income = await create_income(session, user.id, 40000 * 100, today, "Income")
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=None,
                    amount=20000 * 100,
                    transaction_type="manual_adjustment",
                    source="manual",
                    period_date=date(2026, 5, 30),
                )
                await session.commit()

                result = await allocation_service.process_received_income(session, user.id, income.id, today)
                obligation_ids = [item.obligation_id for item in result.items]

                assert obligation_ids == list(dict.fromkeys(obligation_ids))
                assert [item.period_date for item in result.items if item.obligation_id == obligation.id] == [
                    date(2026, 5, 30)
                ]
        finally:
            await engine.dispose()

    run(scenario())


def test_after_current_period_is_closed_next_income_can_reserve_next_period():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(
                    session,
                    user.id,
                    40000 * 100,
                    date(2026, 5, 30),
                    "Alpha Credit",
                )
                income = await create_income(session, user.id, 40000 * 100, date(2026, 6, 20), "June Income")
                await reserves_repo.create(
                    session,
                    user_id=user.id,
                    obligation_id=obligation.id,
                    income_id=None,
                    amount=40000 * 100,
                    transaction_type="manual_adjustment",
                    source="manual",
                    period_date=date(2026, 5, 30),
                )
                await session.commit()

                result = await allocation_service.process_received_income(session, user.id, income.id, today)

                assert [item.period_date for item in result.items if item.obligation_id == obligation.id] == [
                    date(2026, 6, 30)
                ]
        finally:
            await engine.dispose()

    run(scenario())
