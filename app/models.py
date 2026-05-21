from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    obligations: Mapped[list["Obligation"]] = relationship(back_populates="user")


class Obligation(Base, TimestampMixin):
    __tablename__ = "obligations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), default="credit")
    monthly_payment_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_debt_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="obligations")


class Income(Base, TimestampMixin):
    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    income_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="expected")
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    obligation_id: Mapped[int] = mapped_column(ForeignKey("obligations.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReserveTransaction(Base):
    __tablename__ = "reserve_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    obligation_id: Mapped[int | None] = mapped_column(ForeignKey("obligations.id"), nullable=True, index=True)
    income_id: Mapped[int | None] = mapped_column(ForeignKey("incomes.id"), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, default="auto_plan", server_default="auto_plan")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    obligation_id: Mapped[int] = mapped_column(ForeignKey("obligations.id"), index=True)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sent_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSavingsSettings(Base, TimestampMixin):
    __tablename__ = "user_savings_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    percent: Mapped[int] = mapped_column(Integer, default=10)


class SavingsTransaction(Base):
    __tablename__ = "savings_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    income_id: Mapped[int | None] = mapped_column(ForeignKey("incomes.id"), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserLivingMinimumSettings(Base, TimestampMixin):
    __tablename__ = "user_living_minimum_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    period_type: Mapped[str] = mapped_column(String(32), default="until_next_income")
