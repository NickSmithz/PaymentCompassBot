from app.texts import (
    BTN_ADD_INCOME,
    BTN_ADD_OBLIGATION,
    BTN_EDIT,
    BTN_FINANCIAL_STATUS,
    BTN_MY_INCOMES,
    BTN_UPCOMING_PAYMENTS,
)
from app.utils import format_date, format_money, risk_emoji, risk_label


def _status_label(status: str) -> str:
    return {"good": "🟢 всё под контролем", "attention": "🟡 нужно внимание", "danger": "🔴 высокий риск"}.get(status, status)


def format_allocation_result(result) -> str:
    lines = [
        f"💰 Расчёт по доходу: {result.income_title} — {format_money(result.income_amount)}",
        "",
        f"Нужно отложить на платежи: {format_money(result.total_to_reserve)}",
    ]
    if result.savings_enabled:
        lines.append(f"В копилку: {format_money(result.actual_savings_amount)}")
    lines.extend(
        [
            f"Можно тратить: {format_money(result.safe_to_spend)}",
            f"Риск просрочки: {risk_emoji(result.overall_risk)} {risk_label(result.overall_risk)}",
        ]
    )
    if result.living_minimum_enabled:
        lines.extend(["", f"Минимум на жизнь: {format_money(result.living_minimum_amount)}"])
        if result.living_minimum_gap > 0:
            lines.append(f"Не хватает до минимума: {format_money(result.living_minimum_gap)}")
        else:
            lines.append(f"Запас сверх минимума: {format_money(result.safe_to_spend - result.living_minimum_amount)}")

    reserved_items = [item for item in result.items if item.recommended_reserve > 0]
    if reserved_items:
        lines.extend(["", "Куда отложить:"])
        for index, item in enumerate(reserved_items, start=1):
            lines.append(f"{index}. {item.title} — {format_money(item.recommended_reserve)} до {format_date(item.due_date)}")

    if result.savings_enabled:
        lines.extend(["", "Копилка:"])
        if result.actual_savings_amount < result.desired_savings_amount:
            lines.append(f"План: {result.savings_percent}% — {format_money(result.desired_savings_amount)}")
            lines.append(f"Получилось отложить: {format_money(result.actual_savings_amount)}")
            lines.append("Причина: сначала закрываем обязательные платежи.")
        else:
            lines.append(f"{result.savings_percent}% от дохода — {format_money(result.actual_savings_amount)}")

    if result.items:
        nearest = min(result.items, key=lambda item: item.due_date)
        lines.extend(["", f"Ближайший платёж: {nearest.title} — {format_date(nearest.due_date)}"])
    if result.warnings:
        lines.extend(["", *[f"⚠️ {warning}" for warning in result.warnings]])
    return "\n".join(lines)


def format_obligations_list(summary) -> str:
    items = summary["items"] if isinstance(summary, dict) else summary
    if not items:
        return f"{BTN_UPCOMING_PAYMENTS}\n\nПока нет добавленных платежей.\n\nДобавь первый платёж через кнопку «{BTN_ADD_OBLIGATION}»."

    lines = [BTN_UPCOMING_PAYMENTS, ""]
    for index, item in enumerate(items, start=1):
        if item["paid_amount"] >= item["amount"]:
            status = "🟢 оплачен"
        elif item["remaining_amount"] == 0:
            status = "🟢 закрыт"
        elif item["days_left"] <= 3:
            status = "🔴 высокий риск"
        elif item["days_left"] <= 7:
            status = "🟡 нужно добрать"
        else:
            status = "⚪ впереди"
        lines.extend(
            [
                f"{index}. {item['title']}",
                f"Сумма: {format_money(item['amount'])}",
                f"Дата: {format_date(item['date'])}",
                f"Уже отложено: {format_money(item['reserved_amount'])}",
                f"Осталось собрать: {format_money(item['remaining_amount'])}",
                f"Статус: {status}",
                "",
            ]
        )
    if isinstance(summary, dict):
        lines.extend(
            [
                "Итого по платежам:",
                f"Всего к оплате: {format_money(summary['total_required'])}",
                f"Уже отложено: {format_money(summary['total_reserved'])}",
                f"Уже оплачено: {format_money(summary['total_paid'])}",
                f"Осталось собрать: {format_money(summary['total_remaining'])}",
            ]
        )
    return "\n".join(lines).strip()


def format_incomes_list(summary) -> str:
    incomes = summary["incomes"] if isinstance(summary, dict) else summary
    if not incomes:
        return f"{BTN_MY_INCOMES}\n\nПока нет добавленных доходов.\n\nДобавь первый доход через кнопку «{BTN_ADD_INCOME}»."

    labels = {"received": "✅ получен", "expected": "⏳ ожидается", "cancelled": "❌ отменён"}
    lines = [BTN_MY_INCOMES, ""]
    for index, income in enumerate(incomes, start=1):
        lines.extend(
            [
                f"{index}. {income.title}",
                f"Сумма: {format_money(income.amount)}",
                f"Дата: {format_date(income.income_date)}",
                f"Статус: {labels.get(income.status, income.status)}",
            ]
        )
        if income.source:
            lines.append(f"Источник: {income.source}")
        lines.append("")

    if isinstance(summary, dict):
        lines.extend(
            [
                "Итого:",
                f"Получено: {format_money(summary['total_received'])}",
                f"Ожидается: {format_money(summary['total_expected'])}",
                f"Всего без отменённых: {format_money(summary['total_all'])}",
            ]
        )
        if summary["total_cancelled"] > 0:
            lines.append(f"Отменено: {format_money(summary['total_cancelled'])}")
        lines.append("")
    lines.append(f"Чтобы изменить или удалить доход, нажми «{BTN_EDIT}».")
    return "\n".join(lines).strip()


def format_living_minimum_summary(summary) -> str:
    settings = summary["settings"]
    if not settings.is_enabled:
        return (
            "🛟 Минимум на жизнь\n\n"
            "Минимум на жизнь сейчас не задан.\n\n"
            "Это сумма, которую важно оставить на обычные расходы до следующего дохода: продукты, транспорт, связь, бытовые траты.\n\n"
            "Например, если до зарплаты тебе нужно минимум 20 000 ₽, бот будет учитывать это в финансовом статусе и предупреждать, если свободных денег меньше."
        )
    return (
        "🛟 Минимум на жизнь\n\n"
        "Минимум включён.\n"
        f"Сумма: {format_money(settings.amount)}\n"
        "Период: до следующего дохода\n\n"
        "Я буду учитывать эту сумму в финансовом статусе и плане до зарплаты."
    )


def format_living_minimum_updated(settings) -> str:
    return f"Готово. Минимум на жизнь установлен: {format_money(settings.amount)} до следующего дохода."


def format_financial_status(summary) -> str:
    if not summary.get("has_income"):
        return (
            f"{BTN_FINANCIAL_STATUS}\n\n"
            "Пока я не могу посчитать финансовый статус.\n\n"
            "Добавь доход со статусом «Уже пришёл», и я покажу:\n"
            "- сколько нужно отложить;\n"
            "- сколько можно тратить;\n"
            "- хватает ли денег до следующего дохода;\n"
            "- есть ли риск просрочки."
        )

    lines = [
        BTN_FINANCIAL_STATUS,
        "",
        f"Состояние: {_status_label(summary['overall_status'])}",
        "",
        "Последний доход:",
        f"{summary['income_title']} — {format_money(summary['income_amount'])} от {format_date(summary['income_date'])}",
        "",
        f"Нужно отложить на платежи: {format_money(summary['total_to_reserve'])}",
    ]
    if summary["savings_enabled"]:
        lines.append(f"В копилку: {format_money(summary['savings_amount'])}")
    else:
        lines.append("Копилка: выключена")
    lines.append(f"Можно тратить: {format_money(summary['safe_to_spend'])}")
    lines.append("")

    if summary["living_minimum_enabled"]:
        lines.append(f"Минимум на жизнь: {format_money(summary['living_minimum_amount'])}")
        if summary["living_minimum_gap"] > 0:
            lines.append(f"Не хватает до минимума: {format_money(summary['living_minimum_gap'])}")
        else:
            lines.append(f"Запас сверх минимума: {format_money(summary['safe_to_spend'] - summary['living_minimum_amount'])}")
    else:
        lines.append("Минимум на жизнь: не задан")

    nearest = summary.get("nearest_obligation")
    if nearest:
        lines.extend(["", "Ближайший платёж:", f"{nearest['title']} — {format_money(nearest['amount'])} до {format_date(nearest['date'])}"])
    lines.extend(["", f"Риск просрочки: {risk_emoji(summary['overall_risk'])} {risk_label(summary['overall_risk'])}", ""])

    header = "Что сделать сейчас:" if summary["overall_status"] != "attention" else "Что можно сделать:"
    lines.append(header)
    for index, recommendation in enumerate(summary["recommendations"], start=1):
        lines.append(f"{index}. {recommendation}")
    return "\n".join(lines)


def format_salary_plan(summary) -> str:
    if not summary.get("has_income"):
        return (
            "📆 План до зарплаты\n\n"
            "Пока не могу составить план.\n\n"
            "Добавь доход со статусом «Уже пришёл», чтобы я понял, от какой суммы считать."
        )
    if not summary.get("has_next_income"):
        return (
            "📆 План до зарплаты\n\n"
            "Пока не вижу следующего дохода.\n\n"
            "Добавь ожидаемый доход, например зарплату или аванс, и я посчитаю, сколько можно тратить в день."
        )

    next_income = summary["next_income"]
    lines = [
        "📆 План до зарплаты",
        "",
        f"До следующего дохода: {summary['days_until_next_income']} дней",
        "Следующий доход:",
        f"{next_income['title']} — {format_money(next_income['amount'])}, {format_date(next_income['date'])}",
        "",
        f"Можно тратить всего: {format_money(summary['safe_to_spend'])}",
        f"Рекомендуемый лимит в день: {format_money(summary['daily_limit'])}",
        "",
    ]
    if summary["living_minimum_enabled"]:
        lines.append(f"Минимум на жизнь: {format_money(summary['living_minimum_amount'])}")
        if summary["living_minimum_gap"] > 0:
            lines.append(f"Не хватает до минимума: {format_money(summary['living_minimum_gap'])}")
        else:
            lines.append(f"Минимум в день: {format_money(summary['living_minimum_daily'])}")
        lines.append("")
    lines.extend([f"Состояние: {_status_label(summary['status'])}", ""])
    if summary["status"] == "danger":
        lines.append("Сначала нужно закрыть ближайшие обязательные платежи. Сейчас свободных денег до следующего дохода нет.")
    else:
        lines.append("Рекомендация:" if summary["status"] == "good" else "Что можно сделать:")
        for index, recommendation in enumerate(summary["recommendations"], start=1):
            prefix = "" if summary["status"] == "good" and len(summary["recommendations"]) == 1 else f"{index}. "
            lines.append(f"{prefix}{recommendation}")
    return "\n".join(lines)


def format_purchase_impact(summary) -> str:
    if not summary.get("can_calculate"):
        return (
            "🛒 Что если купить?\n\n"
            "Пока не могу посчитать влияние покупки.\n\n"
            "Добавь доход со статусом «Уже пришёл», чтобы я понял, от какой свободной суммы считать."
        )

    labels = {
        "can_buy": "🟢 можно купить",
        "be_careful": "🟡 лучше осторожно",
        "better_not": "🔴 лучше не покупать сейчас",
    }
    lines = [
        f"🛒 Что если купить на {format_money(summary['purchase_amount'])}?",
        "",
        f"Рекомендация: {labels.get(summary['recommendation_type'], summary['recommendation_type'])}",
        "",
        f"До покупки можно тратить: {format_money(summary['safe_to_spend_before'])}",
        f"После покупки останется: {format_money(summary['safe_to_spend_after'])}",
    ]
    if summary["overspend_amount"] > 0:
        lines.append(f"Не хватает: {format_money(summary['overspend_amount'])}")

    lines.extend(["", "План до зарплаты:"])
    if summary["has_next_income"]:
        lines.append(f"До следующего дохода: {summary['days_until_next_income']} дней")
        lines.append(f"Лимит в день до покупки: {format_money(summary['daily_limit_before'])}")
        lines.append(f"Лимит в день после покупки: {format_money(summary['daily_limit_after'])}")
    else:
        lines.append("Следующий доход не указан, поэтому дневной лимит посчитать нельзя.")
        lines.append("Добавь ожидаемый доход, чтобы я точнее оценивал покупки.")

    if summary["living_minimum_enabled"]:
        lines.extend(["", f"Минимум на жизнь: {format_money(summary['living_minimum_amount'])}"])
        if summary["living_gap_after"] > 0:
            lines.append(f"Не хватает до минимума после покупки: {format_money(summary['living_gap_after'])}")
        else:
            lines.append(f"Запас после покупки: {format_money(summary['safe_to_spend_after'] - summary['living_minimum_amount'])}")

    if summary["recommendation_type"] == "better_not" and summary["nearest_obligation_title"]:
        lines.extend(
            [
                "",
                "Ближайший платёж:",
                f"{summary['nearest_obligation_title']} — до {format_date(summary['nearest_obligation_date'])}",
                f"Осталось собрать: {format_money(summary['nearest_obligation_remaining'])}",
            ]
        )

    lines.extend(["", f"Риск просрочки: {risk_emoji(summary['risk_after'])} {risk_label(summary['risk_after'])}", "", "Вывод:"])
    if summary["recommendation_type"] == "can_buy":
        lines.append("Покупка не нарушает план. Но после неё дневной лимит станет ниже.")
    elif summary["recommendation_type"] == "be_careful":
        lines.append("Покупка не забирает деньги из обязательных платежей, но снижает запас до следующего дохода.")
        lines.extend(["", "Что можно сделать:"])
        for index, item in enumerate(summary["recommendations"], start=1):
            lines.append(f"{index}. {item}")
    else:
        lines.append("Покупка больше свободной суммы или слишком сильно ухудшает план.")
        lines.extend(["", "Что лучше сделать:"])
        for index, item in enumerate(summary["recommendations"], start=1):
            lines.append(f"{index}. {item}")

    if summary["warnings"]:
        lines.extend(["", *[f"⚠️ {warning}" for warning in summary["warnings"]]])
    return "\n".join(lines)


def format_progress(progress) -> str:
    lines = [
        "📊 Прогресс долгов",
        "",
        f"Всего долгов указано: {format_money(progress['total_debt'])}",
        f"Оплачено через бот: {format_money(progress['total_paid'])}",
        "",
        "По обязательствам:",
    ]
    if not progress["items"]:
        return "Пока нет данных по долгам."
    for index, item in enumerate(progress["items"], start=1):
        debt = format_money(item["total_debt_amount"]) if item["total_debt_amount"] is not None else "не указан"
        lines.extend([f"{index}. {item['title']}", f"Остаток: {debt}", f"Оплачено через бот: {format_money(item['paid_amount'])}", ""])
    if progress["has_unknown_debts"]:
        lines.append("По части платежей остаток долга не указан, поэтому общий прогресс может быть неполным.")
    return "\n".join(lines).strip()


def format_payment_added(payment) -> str:
    return f"Оплата отмечена. Следующая дата платежа: {format_date(payment.next_payment_date)}"


def format_income_added(income) -> str:
    if income.status == "expected":
        return "Доход добавлен как ожидаемый. Я учту его в расчётах."
    return f"Доход добавлен: {income.title} — {format_money(income.amount)}"


def format_obligation_added(obligation) -> str:
    recurring = "да" if obligation.is_recurring else "нет"
    return "\n".join(
        [
            "Готово. Платёж добавлен:",
            f"Название: {obligation.title}",
            f"Сумма: {format_money(obligation.monthly_payment_amount)}",
            f"Ближайшая дата: {format_date(obligation.next_payment_date)}",
            f"Повторяется: {recurring}",
        ]
    )


def format_income_status_update(result) -> str:
    if result is None:
        return format_error()
    if result["allocation"] is not None:
        return format_allocation_result(result["allocation"])
    if result["new_status"] == "expected" and result["reserves_released"]:
        return "Статус дохода изменён на «Ожидается». Резервы по этому доходу отменены. Данные пересчитаны."
    if result["new_status"] == "cancelled" and result["reserves_released"]:
        return "Доход отменён. Резервы по этому доходу отменены. Данные пересчитаны."
    labels = {"expected": "Ожидается", "received": "Уже пришёл", "cancelled": "Отменён"}
    return f"Статус дохода изменён на «{labels.get(result['new_status'], result['new_status'])}». Рекомендации пересчитаны."


def format_plan_recalculated(entity: str = "Данные") -> str:
    return f"{entity} обновлены. Рекомендации пересчитаны."


def format_reserved_amount_updated(summary) -> str:
    obligation = summary["obligation"]
    old_reserved = summary["old_reserved_amount"]
    new_reserved = summary["new_reserved_amount"]
    delta = summary["delta"]
    remaining = max(0, obligation.monthly_payment_amount - new_reserved)
    message_type = summary["message_type"]
    result = summary.get("recalculation_result")

    if message_type == "unchanged":
        lines = [
            "Сумма «Уже отложено» не изменилась.",
            "",
            f"Платёж: {obligation.title}",
            f"Уже отложено: {format_money(new_reserved)}",
            f"Осталось собрать: {format_money(remaining)}",
        ]
    else:
        change_title = "Увеличение" if message_type == "increased" else "Уменьшение"
        sign = "+" if message_type == "increased" else "-"
        lines = [
            "✅ Сумма «Уже отложено» обновлена.",
            "",
            f"Платёж: {obligation.title}",
            f"Было отложено: {format_money(old_reserved)}",
            f"Стало отложено: {format_money(new_reserved)}",
            f"{change_title}: {sign}{format_money(abs(delta))}",
            "",
            f"Осталось собрать: {format_money(remaining)}",
            "",
            "Финансовые данные пересчитаны.",
        ]

    if result is None:
        lines.extend(["", "Финансовые данные обновлены. Для точного расчёта добавь доход со статусом «Уже пришёл»."])
    elif result.overall_risk in {"medium", "high"}:
        lines.extend(["", f"Текущий риск: {risk_emoji(result.overall_risk)} {risk_label(result.overall_risk)}"])
    return "\n".join(lines)


def format_reserved_amount_validation_error(error) -> str:
    if getattr(error, "code", "") == "too_large":
        return (
            f"Сумма «Уже отложено» не может быть больше суммы платежа: {format_money(error.max_amount)}.\n"
            "Введите сумму ещё раз."
        )
    return "Сумма «Уже отложено» не может быть меньше 0. Введите сумму ещё раз."


def format_savings_summary(summary) -> str:
    settings = summary["settings"]
    if not settings.is_enabled:
        return (
            "🏦 Накопления\n\n"
            "Копилка выключена.\n\n"
            "Копилка помогает автоматически откладывать процент с каждого полученного дохода.\n\n"
            "Рекомендуемый старт — 10% от дохода."
        )
    return (
        "🏦 Накопления\n\n"
        "Копилка включена.\n"
        f"Процент: {settings.percent}%\n\n"
        f"Всего накоплено: {format_money(summary['total_savings'])}\n\n"
        "Как это работает:\n"
        f"с каждого полученного дохода бот откладывает {settings.percent}% в накопления после расчёта обязательных платежей."
    )


def format_savings_history(items) -> str:
    if not items:
        return "История накоплений пока пустая."
    lines = ["🏦 История накоплений", ""]
    for index, (tx, income) in enumerate(items, start=1):
        sign = "-" if tx.transaction_type == "release" else "+"
        title = tx.comment if tx.transaction_type == "release" and tx.comment else (income.title if income else (tx.comment or "накопления"))
        lines.append(f"{index}. {sign}{format_money(tx.amount)} — {title} — {format_date(tx.created_at.date())}")
    return "\n".join(lines)


def format_savings_settings_updated(settings) -> str:
    return (
        f"Копилка включена. Теперь я буду откладывать {settings.percent}% с каждого полученного дохода, "
        "если после обязательных платежей остаются деньги."
    )


def format_help() -> str:
    return (
        "Платёжный Компас помогает понять, сколько денег нужно отложить с каждого дохода, чтобы не пропустить платежи.\n\n"
        "Когда бот рассчитывает, сколько нужно отложить с дохода, он считает эту сумму зарезервированной в плане. "
        "Если фактически ты отложил другую сумму, измени поле «Уже отложено» вручную.\n\n"
        "📍 Финансовый статус — общая сводка: сколько можно тратить, что нужно отложить, есть ли риск просрочки и хватает ли денег на минимум.\n"
        "🛟 Минимум на жизнь — сумма, которую важно оставить на обычные расходы до следующего дохода.\n"
        "📆 План до зарплаты — показывает, сколько можно тратить в день до ближайшего ожидаемого дохода.\n"
        "🛒 Что если купить? — проверяет покупку до оплаты. Введи сумму, а бот покажет, как покупка повлияет на свободные деньги, план до зарплаты, минимум на жизнь и риск просрочки.\n"
        "💵 Мои доходы — список всех добавленных доходов: ожидаемых, полученных и отменённых.\n"
        "🏦 Накопления — копилка, которая помогает откладывать процент с каждого дохода.\n\n"
        "В разделе «Редактировать платежи» можно изменить сумму «Уже отложено». После изменения бот пересчитает ближайшие платежи, финансовый статус и план до зарплаты.\n\n"
        "Если ты начал действие по ошибке, нажми «❌ Отменить действие» или отправь /cancel. Если во время любого действия нажать кнопку главного меню, текущее действие будет автоматически прервано.\n\n"
        "Команды:\n"
        "/start — запустить бота\n"
        "/menu — главное меню\n"
        "/status — финансовый статус\n"
        "/living_minimum — минимум на жизнь\n"
        "/salary_plan — план до зарплаты\n"
        "/what_if_buy — проверить покупку\n"
        "/add_income — добавить доход\n"
        "/incomes — список доходов\n"
        "/savings — накопления\n"
        "/add_obligation — добавить платёж\n"
        "/spend — сколько можно тратить\n"
        "/payments — ближайшие платежи\n"
        "/progress — прогресс долгов\n"
        "/help — помощь\n\n"
        "Бот помогает с личным планированием и не является финансовой, юридической или инвестиционной консультацией."
    )


def format_error() -> str:
    return "Что-то пошло не так. Попробуй ещё раз или вернись в меню командой /menu."


def format_reminder(data) -> str:
    title = data["title"]
    amount = format_money(data["amount"])
    reserved = format_money(data["reserved_amount"])
    remaining = format_money(data["remaining_amount"])
    days = data["days_left"]
    if days < 0:
        return f"Платёж просрочен: {title}.\nДата была: {format_date(data['date'])}.\nОсталось собрать: {remaining}.\nРиск: 🔴 высокий."
    if days == 0:
        return f"Сегодня платёж: {title} — {amount}.\nНе забудь оплатить и отметить оплату в боте."
    if days == 1:
        return f"Завтра платёж: {title} — {amount}.\nОсталось собрать: {remaining}.\nРиск: 🟡 средний."
    return f"Через {days} дней платёж: {title} — {amount}.\nУже отложено: {reserved}.\nОсталось собрать: {remaining}."

