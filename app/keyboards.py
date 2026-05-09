from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.texts import (
    BTN_ADD_INCOME,
    BTN_ADD_OBLIGATION,
    BTN_BACK,
    BTN_CANCEL_ACTION,
    BTN_EDIT,
    BTN_FINANCIAL_STATUS,
    BTN_LIVING_MINIMUM,
    BTN_MARK_PAYMENT,
    BTN_MENU,
    BTN_MY_INCOMES,
    BTN_PROGRESS,
    BTN_SAFE_TO_SPEND,
    BTN_SALARY_PLAN,
    BTN_SAVINGS,
    BTN_SETTINGS,
    BTN_UPCOMING_PAYMENTS,
    BTN_WHAT_IF_BUY,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_FINANCIAL_STATUS)],
        [KeyboardButton(text=BTN_SAFE_TO_SPEND), KeyboardButton(text=BTN_WHAT_IF_BUY)],
        [KeyboardButton(text=BTN_SALARY_PLAN), KeyboardButton(text=BTN_LIVING_MINIMUM)],
        [KeyboardButton(text=BTN_ADD_INCOME), KeyboardButton(text=BTN_MY_INCOMES)],
        [KeyboardButton(text=BTN_ADD_OBLIGATION), KeyboardButton(text=BTN_UPCOMING_PAYMENTS)],
        [KeyboardButton(text=BTN_SAVINGS), KeyboardButton(text=BTN_MARK_PAYMENT)],
        [KeyboardButton(text=BTN_PROGRESS), KeyboardButton(text=BTN_EDIT)],
        [KeyboardButton(text=BTN_SETTINGS)],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def _inline(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data) for text, data in row] for row in rows]
    )


def obligation_type_keyboard() -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Кредит", "otype:credit"), ("Кредитка", "otype:credit_card")],
            [("Рассрочка", "otype:installment"), ("Ипотека", "otype:mortgage")],
            [("Долг человеку", "otype:personal_debt"), ("ЖКХ", "otype:utilities")],
            [("Аренда", "otype:rent"), ("Другое", "otype:other")],
        ]
    )


def recurring_keyboard() -> InlineKeyboardMarkup:
    return _inline([[("Да", "recurring:yes"), ("Нет", "recurring:no")]])


def income_status_keyboard() -> InlineKeyboardMarkup:
    return _inline([[("Уже пришёл", "income_status:received"), ("Ожидается", "income_status:expected")]])


def today_keyboard(prefix: str = "today") -> InlineKeyboardMarkup:
    return _inline([[("Сегодня", prefix)]])


def priority_keyboard() -> InlineKeyboardMarkup:
    return _inline([[("Высокий", "priority:1"), ("Средний", "priority:2"), ("Обычный", "priority:3")]])


def edit_menu_keyboard() -> InlineKeyboardMarkup:
    return _inline(
        [
            [("💵 Редактировать доходы", "edit:incomes"), ("📅 Редактировать платежи", "edit:obligations")],
            [("🗑 Удалить доход", "edit:delete_income"), ("🗑 Отключить платёж", "edit:delete_obligation")],
            [(BTN_BACK, "edit:back")],
        ]
    )


def obligations_inline_keyboard(obligations, prefix: str) -> InlineKeyboardMarkup:
    rows = [[(obligation.title, f"{prefix}:{obligation.id}")] for obligation in obligations]
    rows.append([(BTN_BACK, "back")])
    return _inline(rows)


def incomes_inline_keyboard(incomes, prefix: str) -> InlineKeyboardMarkup:
    rows = [[(income.title, f"{prefix}:{income.id}")] for income in incomes]
    rows.append([(BTN_BACK, "back")])
    return _inline(rows)


def back_keyboard() -> InlineKeyboardMarkup:
    return _inline([[(BTN_BACK, "back")]])


def cancel_action_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL_ACTION), KeyboardButton(text=BTN_MENU)]],
        resize_keyboard=True,
        input_field_placeholder="Введите данные или отмените действие",
    )


def edit_obligation_fields_keyboard(obligation_id: int) -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Название", f"edit_obl_field:{obligation_id}:title"), ("Тип", f"edit_obl_field:{obligation_id}:type")],
            [("Сумма платежа", f"edit_obl_field:{obligation_id}:amount")],
            [("Ближайшая дата", f"edit_obl_field:{obligation_id}:date")],
            [("Уже отложено", f"edit_obl_field:{obligation_id}:reserved_amount")],
            [("Остаток долга", f"edit_obl_field:{obligation_id}:debt")],
            [("Приоритет", f"edit_obl_field:{obligation_id}:priority")],
            [("Регулярность", f"edit_obl_field:{obligation_id}:recurring")],
            [("Статус платежа", f"edit_obl_field:{obligation_id}:status")],
            [(BTN_BACK, "edit:back")],
        ]
    )


def edit_income_fields_keyboard(income_id: int) -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Название", f"edit_inc_field:{income_id}:title"), ("Сумма", f"edit_inc_field:{income_id}:amount")],
            [("Дата", f"edit_inc_field:{income_id}:date"), ("Статус", f"edit_inc_field:{income_id}:status")],
            [("Источник", f"edit_inc_field:{income_id}:source")],
            [(BTN_BACK, "edit:back")],
        ]
    )


def settings_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    text = "Выключить уведомления" if enabled else "Включить уведомления"
    return _inline([[(text, "settings:toggle_reminders")], [("Помощь", "settings:help")]])


def income_status_edit_keyboard(income_id: int) -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Ожидается", f"edit_inc_status:{income_id}:expected")],
            [("Уже пришёл", f"edit_inc_status:{income_id}:received")],
            [("Отменён", f"edit_inc_status:{income_id}:cancelled")],
            [(BTN_BACK, "edit:back")],
        ]
    )


def obligation_status_keyboard(obligation_id: int) -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Активен", f"edit_obl_status:{obligation_id}:active")],
            [("Отключён", f"edit_obl_status:{obligation_id}:disabled")],
            [(BTN_BACK, "edit:back")],
        ]
    )


def obligation_recurring_keyboard(obligation_id: int) -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Повторяется", f"edit_obl_recurring:{obligation_id}:yes")],
            [("Не повторяется", f"edit_obl_recurring:{obligation_id}:no")],
            [(BTN_BACK, "edit:back")],
        ]
    )


def savings_disabled_keyboard() -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Включить копилку 10%", "savings:enable_10")],
            [("Выбрать свой процент", "savings:custom_percent")],
            [(BTN_BACK, "back")],
        ]
    )


def savings_enabled_keyboard() -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Изменить процент", "savings:custom_percent")],
            [("Отключить копилку", "savings:disable")],
            [("История накоплений", "savings:history")],
            [(BTN_BACK, "back")],
        ]
    )


def living_minimum_disabled_keyboard() -> InlineKeyboardMarkup:
    return _inline([[("Задать минимум", "living:set")], [(BTN_BACK, "back")]])


def living_minimum_enabled_keyboard() -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Изменить сумму", "living:set")],
            [("Отключить минимум", "living:disable")],
            [(BTN_BACK, "back")],
        ]
    )


def purchase_impact_keyboard(recommendation_type: str) -> InlineKeyboardMarkup:
    rows = [
        [("Проверить другую сумму", "what_if:again")],
        [("Добавить доход", "what_if:add_income"), ("План до зарплаты", "what_if:salary_plan")],
    ]
    if recommendation_type == "better_not":
        rows.append([("Посмотреть ближайшие платежи", "what_if:payments")])
    rows.append([(BTN_MENU, "back")])
    return _inline(rows)

