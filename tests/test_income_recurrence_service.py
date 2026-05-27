import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Income, User
from app.services import income_recurrence, incomes as income_service, return_flow as return_flow_service


def run(coro):
    return asyncio.run(coro)


async def make_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def create_user(session, telegram_id: int = 7001) -> User:
    user = User(telegram_id=telegram_id, username="test", first_name="Test")
    session.add(user)
    await session.flush()
    return user


async def create_recurring_income(session, user_id: int, day: date, status: str = "expected") -> Income:
    income = await income_service.create_income(
        session,
        user_id,
        {
            "title": "Peskostruy",
            "amount": 40000 * 100,
            "income_date": day,
            "period_date": day,
            "status": status,
            "is_recurring": True,
            "recurrence_type": "monthly",
        },
        now=datetime(2026, 5, 28, 12, 0),
    )
    return income


async def income_count(session, user_id: int) -> int:
    return await session.scalar(select(func.count(Income.id)).where(Income.user_id == user_id)) or 0


def test_create_recurring_income_sets_parent_and_period_date():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                income = await create_recurring_income(session, user.id, date(2026, 5, 26))

                assert income.parent_income_id == income.id
                assert income.period_date == date(2026, 5, 26)
                assert income.is_recurring
        finally:
            await engine.dispose()

    run(scenario())


def test_ensure_income_instances_creates_next_month():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                root = await create_recurring_income(session, user.id, date(2026, 5, 26))

                await income_recurrence.ensure_income_instances(session, user.id, date(2026, 5, 28))
                instances = await session.scalars(select(Income).where(Income.parent_income_id == root.id))
                dates = sorted(income.period_date for income in instances)

                assert dates == [date(2026, 5, 26), date(2026, 6, 26)]
        finally:
            await engine.dispose()

    run(scenario())


def test_ensure_income_instances_does_not_create_duplicates():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                await create_recurring_income(session, user.id, date(2026, 5, 26))

                for _ in range(3):
                    await income_recurrence.ensure_income_instances(session, user.id, date(2026, 5, 28))

                assert await income_count(session, user.id) == 2
        finally:
            await engine.dispose()

    run(scenario())


def test_received_regular_income_creates_next_expected_instance():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            now = datetime(2026, 5, 28, 12, 0)
            async with Session() as session:
                user = await create_user(session)
                root = await create_recurring_income(session, user.id, date(2026, 5, 26), status="expected")

                await income_service.update_income_status(session, user.id, root.id, "received", now.date(), now)
                instances = await session.scalars(select(Income).where(Income.parent_income_id == root.id))
                by_period = {income.period_date: income for income in instances}

                assert by_period[date(2026, 5, 26)].status == "received"
                assert by_period[date(2026, 5, 26)].received_at == now
                assert by_period[date(2026, 6, 26)].status == "expected"
                assert by_period[date(2026, 6, 26)].received_at is None
        finally:
            await engine.dispose()

    run(scenario())


def test_next_month_income_has_separate_id_and_processing_target():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            now = datetime(2026, 6, 26, 12, 0)
            async with Session() as session:
                user = await create_user(session)
                may_income = await create_recurring_income(session, user.id, date(2026, 5, 26), status="received")
                await income_recurrence.ensure_income_instances(session, user.id, date(2026, 5, 28))
                june_income = await session.scalar(
                    select(Income).where(
                        Income.parent_income_id == may_income.id,
                        Income.period_date == date(2026, 6, 26),
                    )
                )

                await income_service.update_income_status(session, user.id, june_income.id, "received", now.date(), now)
                await session.refresh(may_income)
                await session.refresh(june_income)

                assert june_income.id != may_income.id
                assert may_income.period_date == date(2026, 5, 26)
                assert june_income.period_date == date(2026, 6, 26)
                assert june_income.received_at == now
        finally:
            await engine.dispose()

    run(scenario())


def test_return_flow_marks_old_instance_without_received_at_and_creates_future_instance():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            async with Session() as session:
                user = await create_user(session)
                root = await create_recurring_income(session, user.id, date(2026, 5, 26), status="expected")

                await return_flow_service.apply_return_flow(session, user.id, today)
                instances = await session.scalars(select(Income).where(Income.parent_income_id == root.id))
                by_period = {income.period_date: income for income in instances}

                assert by_period[date(2026, 5, 26)].status == "received"
                assert by_period[date(2026, 5, 26)].received_at is None
                assert by_period[date(2026, 6, 26)].status == "expected"
        finally:
            await engine.dispose()

    run(scenario())


def test_month_end_income_uses_safe_next_month_date():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                root = await create_recurring_income(session, user.id, date(2026, 5, 31))

                await income_recurrence.ensure_income_instances(session, user.id, date(2026, 5, 31))
                instances = await session.scalars(select(Income).where(Income.parent_income_id == root.id))
                dates = sorted(income.period_date for income in instances)

                assert dates == [date(2026, 5, 31), date(2026, 6, 30)]
        finally:
            await engine.dispose()

    run(scenario())
