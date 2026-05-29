from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        user_columns = await conn.execute(text("PRAGMA table_info(users)"))
        user_column_names = {row[1] for row in user_columns.fetchall()}
        if "last_activity_at" not in user_column_names:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_activity_at DATETIME"))
        if "last_return_prompt_at" not in user_column_names:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_return_prompt_at DATETIME"))
        if "last_focus_income_id" not in user_column_names:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_focus_income_id INTEGER"))

        income_columns = await conn.execute(text("PRAGMA table_info(incomes)"))
        income_column_names = {row[1] for row in income_columns.fetchall()}
        if "received_at" not in income_column_names:
            await conn.execute(text("ALTER TABLE incomes ADD COLUMN received_at DATETIME NULL"))
        if "is_recurring" not in income_column_names:
            await conn.execute(text("ALTER TABLE incomes ADD COLUMN is_recurring BOOLEAN DEFAULT 0"))
        if "recurrence_type" not in income_column_names:
            await conn.execute(text("ALTER TABLE incomes ADD COLUMN recurrence_type VARCHAR(32)"))
        if "parent_income_id" not in income_column_names:
            await conn.execute(text("ALTER TABLE incomes ADD COLUMN parent_income_id INTEGER"))
        if "period_date" not in income_column_names:
            await conn.execute(text("ALTER TABLE incomes ADD COLUMN period_date DATE"))
        await conn.execute(text("UPDATE incomes SET period_date = income_date WHERE period_date IS NULL"))

        columns = await conn.execute(text("PRAGMA table_info(reserve_transactions)"))
        column_names = {row[1] for row in columns.fetchall()}
        if "source" not in column_names:
            await conn.execute(
                text("ALTER TABLE reserve_transactions ADD COLUMN source VARCHAR(32) DEFAULT 'auto_plan'")
            )
        if "period_date" not in column_names:
            await conn.execute(text("ALTER TABLE reserve_transactions ADD COLUMN period_date DATE"))
        await conn.execute(
            text(
                """
                UPDATE reserve_transactions
                SET period_date = (
                    SELECT obligations.next_payment_date
                    FROM obligations
                    WHERE obligations.id = reserve_transactions.obligation_id
                )
                WHERE period_date IS NULL
                  AND obligation_id IS NOT NULL
                """
            )
        )

        payment_columns = await conn.execute(text("PRAGMA table_info(payment_records)"))
        payment_column_names = {row[1] for row in payment_columns.fetchall()}
        if "period_date" not in payment_column_names:
            await conn.execute(text("ALTER TABLE payment_records ADD COLUMN period_date DATE"))


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
