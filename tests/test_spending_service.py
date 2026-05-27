import asyncio
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Income, ReserveTransaction, User
from app.services import spending as spending_service


def run(coro):
    return asyncio.run(coro)


async def make_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def create_user(session, telegram_id: int = 3001) -> User:
    user = User(telegram_id=telegram_id, username="test", first_name="Test")
    session.add(user)
    await session.flush()
    return user


async def create_income(session, user_id: int, amount_rub: int, day: date, status: str = "received", title: str = "Доход") -> Income:
    income = Income(user_id=user_id, title=title, amount=amount_rub * 100, income_date=day, status=status)
    session.add(income)
    await session.flush()
    return income


async def create_auto_reserve(session, user_id: int, income_id: int, amount_rub: int, transaction_type: str = "reserve") -> ReserveTransaction:
    tx = ReserveTransaction(
        user_id=user_id,
        income_id=income_id,
        obligation_id=1,
        amount=amount_rub * 100,
        transaction_type=transaction_type,
        source="auto_plan",
        comment="Автоматическое резервирование с дохода",
    )
    session.add(tx)
    await session.flush()
    return tx


async def reserve_count(session) -> int:
    return await session.scalar(select(func.count(ReserveTransaction.id))) or 0


def test_multiple_received_incomes_today_are_summarized():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            async with Session() as session:
                user = await create_user(session)
                first = await create_income(session, user.id, 30000, today, title="Юнона")
                second = await create_income(session, user.id, 25000, today, title="Аксенова")
                await create_auto_reserve(session, user.id, first.id, 19808)
                await create_auto_reserve(session, user.id, second.id, 14365)
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today)

                assert summary["type"] == "today_multiple"
                assert summary["total_income"] == 55000 * 100
                assert summary["total_reserved"] == 34173 * 100
                assert summary["total_safe_to_spend"] == 20827 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_single_received_income_today_is_single_income_summary():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id, 30000, today, title="Юнона")
                await create_auto_reserve(session, user.id, income.id, 19808)
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today)

                assert summary["type"] == "single_income"
                assert summary["incomes"][0]["income_id"] == income.id
                assert summary["total_safe_to_spend"] == 10192 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_last_received_income_is_used_when_today_has_no_received_income():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            async with Session() as session:
                user = await create_user(session)
                old_income = await create_income(session, user.id, 30000, today - timedelta(days=10), title="Юнона")
                await create_auto_reserve(session, user.id, old_income.id, 19808)
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today)

                assert summary["type"] == "last_income"
                assert summary["incomes"][0]["income_id"] == old_income.id
                assert summary["total_reserved"] == 19808 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_no_received_income_returns_no_income_summary():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            async with Session() as session:
                user = await create_user(session)
                await create_income(session, user.id, 30000, today, status="expected")
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today)

                assert summary["type"] == "no_income"
                assert summary["incomes"] == []
                assert summary["total_safe_to_spend"] == 0
        finally:
            await engine.dispose()

    run(scenario())


def test_spending_summary_does_not_create_reserve_transactions():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id, 30000, today, title="Юнона")
                await create_auto_reserve(session, user.id, income.id, 19808)
                await session.commit()

                before = await reserve_count(session)
                await spending_service.get_spending_summary(session, user.id, today)
                after = await reserve_count(session)

                assert before == after == 1
        finally:
            await engine.dispose()

    run(scenario())
