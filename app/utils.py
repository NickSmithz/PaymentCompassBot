import calendar
import math
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def parse_money(text: str) -> int:
    value = text.strip().lower().replace("₽", "").replace("руб", "").replace(" ", "")
    multiplier = 100
    if value.endswith(("к", "k")):
        multiplier *= 1000
        value = value[:-1]
    value = value.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?", value):
        raise ValueError("Некорректная сумма")
    return int(math.ceil(float(value) * multiplier))


def format_money(amount: int) -> str:
    rubles = amount // 100
    return f"{rubles:,}".replace(",", " ") + " ₽"


def parse_date(text: str, timezone: str) -> date:
    raw = text.strip().lower()
    today = datetime.now(ZoneInfo(timezone)).date()
    if raw == "сегодня":
        return today
    if raw == "завтра":
        return today + timedelta(days=1)
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    try:
        parsed = datetime.strptime(raw, "%d.%m").date().replace(year=today.year)
    except ValueError as exc:
        raise ValueError("Некорректная дата") from exc
    if parsed < today:
        parsed = parsed.replace(year=today.year + 1)
    return parsed


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def add_month(value: date, preferred_day: int | None = None) -> date:
    month = value.month + 1
    year = value.year
    if month == 13:
        month = 1
        year += 1
    day = min(preferred_day or value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def risk_emoji(risk: str) -> str:
    return {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "⚪")


def risk_label(risk: str) -> str:
    return {"low": "низкий", "medium": "средний", "high": "высокий"}.get(risk, risk)
