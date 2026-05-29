import asyncio
from datetime import date
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.keyboards import income_status_change_button_text
from app.models import Base, Income, User
from app.repositories import incomes as incomes_repo


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


async def create_income(
    session,
    user_id: int,
    title: str,
    income_date: date,
    status: str = "expected",
    period_date: date | None = None,
) -> Income:
    income = Income(
        user_id=user_id,
        title=title,
        amount=30000 * 100,
        income_date=income_date,
        period_date=period_date,
        status=status,
    )
    session.add(income)
    await session.flush()
    return income


def test_status_change_list_returns_only_expected_incomes():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                await create_income(session, user.id, "Received", date(2026, 5, 26), status="received")
                expected = await create_income(session, user.id, "Expected", date(2026, 6, 10), status="expected")
                await create_income(session, user.id, "Cancelled", date(2026, 6, 15), status="cancelled")
                await session.commit()

                incomes = await incomes_repo.list_incomes_for_status_change(session, user.id)

                assert [income.id for income in incomes] == [expected.id]
        finally:
            await engine.dispose()

    run(scenario())


def test_status_change_list_sorts_from_earliest_to_latest():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                income_20 = await create_income(session, user.id, "20", date(2026, 6, 20))
                income_10 = await create_income(session, user.id, "10", date(2026, 6, 10))
                income_25 = await create_income(session, user.id, "25", date(2026, 6, 25))
                await session.commit()

                incomes = await incomes_repo.list_incomes_for_status_change(session, user.id)

                assert [income.id for income in incomes] == [income_10.id, income_20.id, income_25.id]
        finally:
            await engine.dispose()

    run(scenario())


def test_status_change_list_sorts_by_period_date_before_income_date():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                recurring_instance = await create_income(
                    session,
                    user.id,
                    "Peskostruy",
                    date(2026, 5, 26),
                    period_date=date(2026, 6, 26),
                )
                earlier = await create_income(session, user.id, "Yuneko", date(2026, 6, 10), period_date=date(2026, 6, 10))
                await session.commit()

                incomes = await incomes_repo.list_incomes_for_status_change(session, user.id)

                assert [income.id for income in incomes] == [earlier.id, recurring_instance.id]
        finally:
            await engine.dispose()

    run(scenario())


def test_status_change_list_uses_id_for_same_date_stable_order():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                first = await create_income(session, user.id, "First", date(2026, 6, 25), period_date=date(2026, 6, 25))
                second = await create_income(session, user.id, "Second", date(2026, 6, 25), period_date=date(2026, 6, 25))
                await session.commit()

                incomes = await incomes_repo.list_incomes_for_status_change(session, user.id)

                assert [income.id for income in incomes] == [first.id, second.id]
        finally:
            await engine.dispose()

    run(scenario())


def test_status_change_button_text_contains_date_title_and_amount():
    income = SimpleNamespace(
        title="Peskostruy",
        amount=40000 * 100,
        income_date=date(2026, 5, 26),
        period_date=date(2026, 6, 26),
    )

    text = income_status_change_button_text(income)

    assert text.startswith("26.06")
    assert "Peskostruy" in text
    assert "40 000" in text
