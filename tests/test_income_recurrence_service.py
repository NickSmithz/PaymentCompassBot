import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Income, ReserveTransaction, User
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


async def create_plain_income(
    session,
    user_id: int,
    day: date,
    title: str = "Income",
    status: str = "expected",
    recurrence_type: str | None = None,
) -> Income:
    income = Income(
        user_id=user_id,
        title=title,
        amount=40000 * 100,
        income_date=day,
        status=status,
        is_recurring=False,
        recurrence_type=recurrence_type,
    )
    session.add(income)
    await session.flush()
    return income


async def income_count(session, user_id: int) -> int:
    return await session.scalar(select(func.count(Income.id)).where(Income.user_id == user_id)) or 0


async def reserve_count(session, user_id: int) -> int:
    return await session.scalar(select(func.count(ReserveTransaction.id)).where(ReserveTransaction.user_id == user_id)) or 0


async def count_income_instances(session, user_id: int, parent_income_id: int, period: date) -> int:
    return (
        await session.scalar(
            select(func.count(Income.id)).where(
                Income.user_id == user_id,
                Income.parent_income_id == parent_income_id,
                Income.period_date == period,
            )
        )
        or 0
    )


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


def test_normalize_all_existing_incomes_marks_user_incomes_recurring():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                income1 = await create_plain_income(
                    session,
                    user.id,
                    date(2026, 5, 26),
                    title="Peskostruy",
                    recurrence_type="monthly",
                )
                income2 = await create_plain_income(session, user.id, date(2026, 5, 28), title="Sport")

                summary = await income_recurrence.normalize_all_existing_incomes_as_recurring(session, user.id)
                await session.refresh(income1)
                await session.refresh(income2)

                assert summary["incomes_made_recurring"] == 2
                assert income1.is_recurring is True
                assert income2.is_recurring is True
                assert income1.parent_income_id == income1.id
                assert income2.parent_income_id == income2.id
                assert income1.recurrence_type == "monthly"
                assert income2.recurrence_type == "monthly"
                assert income1.period_date == date(2026, 5, 26)
                assert income2.period_date == date(2026, 5, 28)
        finally:
            await engine.dispose()

    run(scenario())


def test_normalize_then_ensure_creates_future_instances_without_duplicates():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                root = await create_plain_income(
                    session,
                    user.id,
                    date(2026, 5, 26),
                    title="Peskostruy",
                    status="received",
                    recurrence_type="monthly",
                )

                for _ in range(3):
                    await income_recurrence.normalize_all_existing_incomes_as_recurring(session, user.id)
                    await income_recurrence.ensure_income_instances(session, user.id, date(2026, 5, 28))

                await session.refresh(root)
                assert await count_income_instances(session, user.id, root.id, date(2026, 6, 26)) == 1
                june_income = await session.scalar(
                    select(Income).where(
                        Income.user_id == user.id,
                        Income.parent_income_id == root.id,
                        Income.period_date == date(2026, 6, 26),
                    )
                )
                assert june_income.status == "expected"
                assert june_income.received_at is None
        finally:
            await engine.dispose()

    run(scenario())


def test_new_one_time_income_does_not_get_monthly_recurrence_type():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                income = await income_service.create_income(
                    session,
                    user.id,
                    {
                        "title": "One time",
                        "amount": 10000 * 100,
                        "income_date": date(2026, 5, 29),
                        "status": "expected",
                        "is_recurring": False,
                        "recurrence_type": "monthly",
                    },
                    now=datetime(2026, 5, 29, 12, 0),
                )

                assert income.is_recurring is False
                assert income.recurrence_type is None
                assert income.parent_income_id is None
                assert income.period_date == date(2026, 5, 29)
        finally:
            await engine.dispose()

    run(scenario())


def test_new_recurring_income_gets_monthly_recurrence_type():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                income = await create_recurring_income(session, user.id, date(2026, 5, 26))

                assert income.is_recurring is True
                assert income.recurrence_type == "monthly"
                assert income.parent_income_id == income.id
                assert income.period_date == date(2026, 5, 26)
        finally:
            await engine.dispose()

    run(scenario())


def test_normalization_and_ensure_do_not_create_reserve_transactions():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                await create_plain_income(
                    session,
                    user.id,
                    date(2026, 5, 26),
                    title="Peskostruy",
                    status="received",
                    recurrence_type="monthly",
                )

                assert await reserve_count(session, user.id) == 0
                await income_recurrence.normalize_all_existing_incomes_as_recurring(session, user.id)
                await income_recurrence.ensure_income_instances(session, user.id, date(2026, 5, 28))

                assert await reserve_count(session, user.id) == 0
        finally:
            await engine.dispose()

    run(scenario())
