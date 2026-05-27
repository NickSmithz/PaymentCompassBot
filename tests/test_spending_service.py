import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Income, ReserveTransaction, User
from app.services import incomes as income_service
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


async def create_income(
    session,
    user_id: int,
    amount_rub: int,
    day: date,
    status: str = "received",
    title: str = "Доход",
    received_at: datetime | None = None,
) -> Income:
    income = Income(
        user_id=user_id,
        title=title,
        amount=amount_rub * 100,
        income_date=day,
        status=status,
        received_at=received_at,
    )
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
            now = datetime(2026, 5, 28, 14, 32)
            async with Session() as session:
                user = await create_user(session)
                first = await create_income(session, user.id, 30000, today, title="Юнона", received_at=now)
                second = await create_income(session, user.id, 25000, today - timedelta(days=1), title="Аксенова", received_at=now)
                await create_auto_reserve(session, user.id, first.id, 19808)
                await create_auto_reserve(session, user.id, second.id, 14365)
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today, now)

                assert summary["type"] == "recent_multiple"
                assert summary["total_income"] == 55000 * 100
                assert summary["total_reserved"] == 34173 * 100
                assert summary["total_safe_to_spend"] == 20827 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_today_multiple_has_priority_over_last_focus_income():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            now = datetime(2026, 5, 28, 14, 32)
            async with Session() as session:
                user = await create_user(session)
                sandblast = await create_income(session, user.id, 40000, date(2026, 5, 26), title="Пескоструй", received_at=now - timedelta(minutes=1))
                sport = await create_income(session, user.id, 40000, date(2026, 5, 28), title="СпортЭталон", received_at=now)
                user.last_focus_income_id = sport.id
                await create_auto_reserve(session, user.id, sandblast.id, 27529)
                await create_auto_reserve(session, user.id, sport.id, 29621)
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today, now)

                assert summary["type"] == "recent_multiple"
                assert {item["income_id"] for item in summary["incomes"]} == {sandblast.id, sport.id}
                assert [item["title"] for item in summary["incomes"]] == ["Пескоструй", "СпортЭталон"]
                assert summary["total_income"] == 80000 * 100
                assert summary["total_reserved"] == 57150 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_single_received_income_today_is_single_today_summary():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            now = datetime(2026, 5, 27, 12, 0)
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id, 30000, today, title="Юнона", received_at=now)
                user.last_focus_income_id = income.id
                await create_auto_reserve(session, user.id, income.id, 19808)
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today, now)

                assert summary["type"] == "recent_single"
                assert summary["incomes"][0]["income_id"] == income.id
                assert summary["total_safe_to_spend"] == 10192 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_invalid_focus_income_falls_back_to_today_received_incomes():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            now = datetime(2026, 5, 27, 12, 0)
            async with Session() as session:
                user = await create_user(session)
                cancelled = await create_income(session, user.id, 10000, today, status="cancelled", title="Отменённый")
                first = await create_income(session, user.id, 30000, today, title="Юнона", received_at=now)
                second = await create_income(session, user.id, 25000, today, title="Аксенова", received_at=now)
                user.last_focus_income_id = cancelled.id
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today, now)

                assert summary["type"] == "recent_multiple"
                assert {item["income_id"] for item in summary["incomes"]} == {first.id, second.id}
        finally:
            await engine.dispose()

    run(scenario())


def test_focus_income_is_used_when_today_has_no_received_income():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            async with Session() as session:
                user = await create_user(session)
                focus_income = await create_income(session, user.id, 25000, today - timedelta(days=5), title="Юнэко")
                older_income = await create_income(session, user.id, 30000, today - timedelta(days=10), title="Спорт Эталон")
                user.last_focus_income_id = focus_income.id
                await create_auto_reserve(session, user.id, focus_income.id, 14365)
                await create_auto_reserve(session, user.id, older_income.id, 19808)
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today)

                assert summary["type"] == "focus_income"
                assert summary["incomes"][0]["income_id"] == focus_income.id
                assert summary["total_reserved"] == 14365 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_last_received_income_is_used_when_today_has_no_received_income_and_focus_is_missing():
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

                assert summary["type"] == "last_received"
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


def test_invalid_focus_income_without_today_received_falls_back_to_last_received():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            async with Session() as session:
                user = await create_user(session)
                cancelled = await create_income(
                    session,
                    user.id,
                    10000,
                    today - timedelta(days=1),
                    status="cancelled",
                    title="Отменённый",
                )
                old_income = await create_income(session, user.id, 30000, today - timedelta(days=10), title="Юнона")
                user.last_focus_income_id = cancelled.id
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today)

                assert summary["type"] == "last_received"
                assert summary["incomes"][0]["income_id"] == old_income.id
        finally:
            await engine.dispose()

    run(scenario())


def test_recent_7d_single_is_used_when_recent_3d_is_empty():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            now = datetime(2026, 5, 28, 14, 32)
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(
                    session,
                    user.id,
                    40000,
                    date(2026, 5, 22),
                    title="СпортЭталон",
                    received_at=now - timedelta(days=5),
                )
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today, now)

                assert summary["type"] == "recent_7d_single"
                assert summary["incomes"][0]["income_id"] == income.id
        finally:
            await engine.dispose()

    run(scenario())


def test_recent_7d_multiple_is_used_when_recent_3d_is_empty():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 28)
            now = datetime(2026, 5, 28, 14, 32)
            async with Session() as session:
                user = await create_user(session)
                first = await create_income(
                    session,
                    user.id,
                    40000,
                    date(2026, 5, 22),
                    title="Пескоструй",
                    received_at=now - timedelta(days=5),
                )
                second = await create_income(
                    session,
                    user.id,
                    40000,
                    date(2026, 5, 23),
                    title="СпортЭталон",
                    received_at=now - timedelta(days=4),
                )
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today, now)

                assert summary["type"] == "recent_7d_multiple"
                assert {item["income_id"] for item in summary["incomes"]} == {first.id, second.id}
        finally:
            await engine.dispose()

    run(scenario())


def test_reserved_for_income_counts_manual_adjustment_and_release():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            now = datetime(2026, 5, 27, 12, 0)
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id, 30000, today, title="Юнона", received_at=now)
                await create_auto_reserve(session, user.id, income.id, 18000)
                await create_auto_reserve(session, user.id, income.id, 1000, transaction_type="manual_adjustment")
                await create_auto_reserve(session, user.id, income.id, 500, transaction_type="release")
                await session.commit()

                summary = await spending_service.get_spending_summary(session, user.id, today, now)

                assert summary["type"] == "recent_single"
                assert summary["total_reserved"] == 18500 * 100
                assert summary["total_safe_to_spend"] == 11500 * 100
        finally:
            await engine.dispose()

    run(scenario())


def test_spending_summary_does_not_create_reserve_transactions():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            now = datetime(2026, 5, 27, 12, 0)
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id, 30000, today, title="Юнона", received_at=now)
                await create_auto_reserve(session, user.id, income.id, 19808)
                await session.commit()

                before = await reserve_count(session)
                await spending_service.get_spending_summary(session, user.id, today, now)
                after = await reserve_count(session)

                assert before == after == 1
        finally:
            await engine.dispose()

    run(scenario())


def test_manual_status_change_to_received_updates_last_focus_income_id():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            now = datetime(2026, 5, 27, 12, 0)
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id, 25000, today, status="expected", title="Юнэко")
                await session.commit()

                await income_service.update_income_status(session, user.id, income.id, "received", today, now)
                await session.refresh(user)
                await session.refresh(income)

                assert user.last_focus_income_id == income.id
                assert income.received_at == now
        finally:
            await engine.dispose()

    run(scenario())


def test_create_received_income_sets_received_at():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            now = datetime(2026, 5, 27, 12, 0)
            async with Session() as session:
                user = await create_user(session)
                income = await income_service.create_income(
                    session,
                    user.id,
                    {
                        "title": "Юнэко",
                        "amount": 25000 * 100,
                        "income_date": today,
                        "status": "received",
                    },
                    now=now,
                )

                assert income.received_at == now
        finally:
            await engine.dispose()

    run(scenario())


def test_status_change_from_received_to_expected_clears_received_at():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            today = date(2026, 5, 27)
            now = datetime(2026, 5, 27, 12, 0)
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(
                    session,
                    user.id,
                    25000,
                    today,
                    status="received",
                    title="Юнэко",
                    received_at=now,
                )
                await session.commit()

                await income_service.update_income_status(session, user.id, income.id, "expected", today, now + timedelta(minutes=1))
                await session.refresh(income)
                summary = await spending_service.get_spending_summary(session, user.id, today, now + timedelta(minutes=1))

                assert income.received_at is None
                assert summary["type"] == "no_income"
        finally:
            await engine.dispose()

    run(scenario())
