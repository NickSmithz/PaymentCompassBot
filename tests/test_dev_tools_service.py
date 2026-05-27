import asyncio
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import (
    Base,
    Income,
    NotificationLog,
    Obligation,
    PaymentRecord,
    ReserveTransaction,
    SavingsTransaction,
    User,
    UserLivingMinimumSettings,
    UserSavingsSettings,
)
from app.services import dev_tools as dev_tools_service


def run(coro):
    return asyncio.run(coro)


async def make_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def create_user(session, telegram_id: int = 5001) -> User:
    user = User(telegram_id=telegram_id, username="test", first_name="Test")
    session.add(user)
    await session.flush()
    return user


async def create_income(session, user_id: int, status: str = "received") -> Income:
    income = Income(user_id=user_id, title="Income", amount=30000 * 100, income_date=date(2026, 5, 27), status=status)
    session.add(income)
    await session.flush()
    return income


async def create_obligation(session, user_id: int, is_active: bool = False) -> Obligation:
    obligation = Obligation(
        user_id=user_id,
        title="Rent",
        type="credit",
        monthly_payment_amount=25000 * 100,
        next_payment_date=date(2026, 6, 5),
        payment_day=5,
        total_debt_amount=100000 * 100,
        priority=3,
        is_active=is_active,
        is_recurring=True,
    )
    session.add(obligation)
    await session.flush()
    return obligation


async def create_payment_record(session, user_id: int, obligation_id: int) -> PaymentRecord:
    record = PaymentRecord(user_id=user_id, obligation_id=obligation_id, amount=5000 * 100, paid_at=date(2026, 5, 20))
    session.add(record)
    await session.flush()
    return record


async def create_reserve_transaction(session, user_id: int, obligation_id: int, income_id: int) -> ReserveTransaction:
    tx = ReserveTransaction(
        user_id=user_id,
        obligation_id=obligation_id,
        income_id=income_id,
        amount=7000 * 100,
        transaction_type="reserve",
        source="auto_plan",
    )
    session.add(tx)
    await session.flush()
    return tx


async def count_by_user(session, model, user_id: int) -> int:
    return await session.scalar(select(func.count(model.id)).where(model.user_id == user_id)) or 0


def test_reset_user_state_keeps_incomes_and_obligations_but_clears_runtime_records():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id, status="received")
                obligation = await create_obligation(session, user.id, is_active=False)
                await create_payment_record(session, user.id, obligation.id)
                await create_reserve_transaction(session, user.id, obligation.id, income.id)
                user.last_focus_income_id = income.id
                user.last_return_prompt_at = datetime(2026, 5, 27, 10, 0)
                await session.commit()

                summary = await dev_tools_service.reset_user_state_for_testing(session, user.id)
                await session.refresh(user)
                await session.refresh(income)
                await session.refresh(obligation)

                assert summary["incomes_reset"] == 1
                assert summary["obligations_activated"] == 1
                assert summary["payment_records_deleted"] == 1
                assert summary["reserve_transactions_deleted"] == 1
                assert summary["last_focus_income_cleared"] is True
                assert income.status == "expected"
                assert obligation.is_active is True
                assert user.last_focus_income_id is None
                assert user.last_return_prompt_at is None
                assert await count_by_user(session, Income, user.id) == 1
                assert await count_by_user(session, Obligation, user.id) == 1
                assert await count_by_user(session, PaymentRecord, user.id) == 0
                assert await count_by_user(session, ReserveTransaction, user.id) == 0
        finally:
            await engine.dispose()

    run(scenario())


def test_clear_user_data_removes_core_and_user_specific_test_records():
    async def scenario():
        engine, Session = await make_session_factory()
        try:
            async with Session() as session:
                user = await create_user(session)
                income = await create_income(session, user.id)
                obligation = await create_obligation(session, user.id, is_active=True)
                await create_payment_record(session, user.id, obligation.id)
                await create_reserve_transaction(session, user.id, obligation.id, income.id)
                session.add(SavingsTransaction(user_id=user.id, income_id=income.id, amount=1000 * 100, transaction_type="reserve"))
                session.add(UserSavingsSettings(user_id=user.id, is_enabled=True, percent=10))
                session.add(UserLivingMinimumSettings(user_id=user.id, is_enabled=True, amount=10000 * 100))
                session.add(
                    NotificationLog(
                        user_id=user.id,
                        obligation_id=obligation.id,
                        notification_type="due_soon",
                        sent_date=date(2026, 5, 27),
                    )
                )
                user.last_focus_income_id = income.id
                user.last_return_prompt_at = datetime(2026, 5, 27, 10, 0)
                await session.commit()

                summary = await dev_tools_service.clear_user_data_for_testing(session, user.id)
                await session.refresh(user)

                assert summary["incomes_deleted"] == 1
                assert summary["obligations_deleted"] == 1
                assert summary["payment_records_deleted"] == 1
                assert summary["reserve_transactions_deleted"] == 1
                assert summary["savings_transactions_deleted"] == 1
                assert summary["notification_logs_deleted"] == 1
                assert summary["settings_deleted"] == 2
                assert user.last_focus_income_id is None
                assert user.last_return_prompt_at is None
                assert await count_by_user(session, Income, user.id) == 0
                assert await count_by_user(session, Obligation, user.id) == 0
                assert await count_by_user(session, PaymentRecord, user.id) == 0
                assert await count_by_user(session, ReserveTransaction, user.id) == 0
                assert await count_by_user(session, SavingsTransaction, user.id) == 0
                assert await count_by_user(session, UserSavingsSettings, user.id) == 0
                assert await count_by_user(session, UserLivingMinimumSettings, user.id) == 0
                assert await count_by_user(session, NotificationLog, user.id) == 0
        finally:
            await engine.dispose()

    run(scenario())
