import asyncio
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Income, Obligation, PaymentRecord, ReserveTransaction, User
from app.services import return_flow as return_flow_service


def run(coro):
    return asyncio.run(coro)


async def make_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def create_user(session, telegram_id: int = 2001) -> User:
    user = User(telegram_id=telegram_id, username="test", first_name="Test")
    session.add(user)
    await session.flush()
    return user


async def create_obligation(
    session,
    user_id: int,
    due: date,
    title: str = "Платёж",
    is_recurring: bool = True,
) -> Obligation:
    obligation = Obligation(
        user_id=user_id,
        title=title,
        type="credit",
        monthly_payment_amount=5000 * 100,
        next_payment_date=due,
        payment_day=due.day,
        total_debt_amount=20000 * 100,
        priority=3,
        is_active=True,
        is_recurring=is_recurring,
    )
    session.add(obligation)
    await session.flush()
    return obligation


async def create_income(session, user_id: int, day: date, status: str = "expected") -> Income:
    income = Income(user_id=user_id, title="Доход", amount=30000 * 100, income_date=day, status=status)
    session.add(income)
    await session.flush()
    return income


async def payment_record_count(session) -> int:
    return await session.scalar(select(func.count(PaymentRecord.id))) or 0


async def reserve_count(session) -> int:
    return await session.scalar(select(func.count(ReserveTransaction.id))) or 0


def test_preview_counts_old_obligations_and_incomes():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 20)
            async with Session() as session:
                user = await create_user(session)
                for index in range(3):
                    await create_obligation(session, user.id, today - timedelta(days=index + 1), f"Платёж {index}")
                for index in range(2):
                    await create_income(session, user.id, today - timedelta(days=index + 1))
                await session.commit()

                preview = await return_flow_service.get_return_preview(session, user.id, today)

                assert preview["overdue_obligations_count"] == 3
                assert preview["past_expected_incomes_count"] == 2
        finally:
            await engine.dispose()

    run(scenario())


def test_today_items_are_not_previewed_or_changed():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 20)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, today)
                income = await create_income(session, user.id, today)
                await session.commit()

                preview = await return_flow_service.get_return_preview(session, user.id, today)
                result = await return_flow_service.apply_return_flow(session, user.id, today)
                await session.refresh(obligation)
                await session.refresh(income)

                assert preview["overdue_obligations_count"] == 0
                assert preview["past_expected_incomes_count"] == 0
                assert result["payments_marked_paid"] == 0
                assert result["incomes_marked_received"] == 0
                assert obligation.next_payment_date == today
                assert income.status == "expected"
                assert await payment_record_count(session) == 0
        finally:
            await engine.dispose()

    run(scenario())


def test_old_obligation_is_marked_paid_with_payment_record():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 20)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, today - timedelta(days=3))
                await session.commit()

                result = await return_flow_service.apply_return_flow(session, user.id, today)

                assert result["payments_marked_paid"] == 1
                assert await payment_record_count(session) == 1
                record = await session.scalar(select(PaymentRecord).where(PaymentRecord.obligation_id == obligation.id))
                assert record.amount == obligation.monthly_payment_amount
                assert record.paid_at == today
        finally:
            await engine.dispose()

    run(scenario())


def test_recurring_obligation_moves_to_nearest_actual_month():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 20)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, date(2026, 4, 20), is_recurring=True)
                await session.commit()

                await return_flow_service.apply_return_flow(session, user.id, today)
                await session.refresh(obligation)

                assert obligation.next_payment_date == today
        finally:
            await engine.dispose()

    run(scenario())


def test_long_absence_moves_recurring_obligation_until_future_or_today():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 20)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, date(2026, 2, 9), is_recurring=True)
                await session.commit()

                await return_flow_service.apply_return_flow(session, user.id, today)
                await session.refresh(obligation)

                assert obligation.next_payment_date == date(2026, 6, 9)
        finally:
            await engine.dispose()

    run(scenario())


def test_old_one_time_obligation_is_deactivated():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 20)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, today - timedelta(days=1), is_recurring=False)
                await session.commit()

                result = await return_flow_service.apply_return_flow(session, user.id, today)
                await session.refresh(obligation)

                assert not obligation.is_active
                assert [item.id for item in result["one_time_obligations_deactivated"]] == [obligation.id]
        finally:
            await engine.dispose()

    run(scenario())


def test_old_expected_income_becomes_received_without_reserves():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 20)
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id, today - timedelta(days=2), status="expected")
                await session.commit()

                before = await reserve_count(session)
                result = await return_flow_service.apply_return_flow(session, user.id, today)
                after = await reserve_count(session)
                await session.refresh(income)

                assert income.status == "received"
                assert income.received_at is None
                assert result["incomes_marked_received"] == 1
                assert before == after == 0
                assert result["reserve_transactions_created"] == 0
        finally:
            await engine.dispose()

    run(scenario())


def test_return_flow_does_not_change_last_focus_income_id():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 20)
            async with Session() as session:
                user = await create_user(session)
                focus_income = await create_income(session, user.id, today, status="received")
                old_income = await create_income(session, user.id, today - timedelta(days=2), status="expected")
                user.last_focus_income_id = focus_income.id
                await session.commit()

                await return_flow_service.apply_return_flow(session, user.id, today)
                await session.refresh(user)
                await session.refresh(old_income)

                assert old_income.status == "received"
                assert user.last_focus_income_id == focus_income.id
        finally:
            await engine.dispose()

    run(scenario())


def test_preview_does_not_change_database_before_confirmation():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 20)
            async with Session() as session:
                user = await create_user(session)
                obligation = await create_obligation(session, user.id, today - timedelta(days=1), is_recurring=False)
                income = await create_income(session, user.id, today - timedelta(days=1), status="expected")
                await session.commit()

                await return_flow_service.get_return_preview(session, user.id, today)
                await session.refresh(obligation)
                await session.refresh(income)

                assert obligation.is_active
                assert income.status == "expected"
                assert await payment_record_count(session) == 0
        finally:
            await engine.dispose()

    run(scenario())
