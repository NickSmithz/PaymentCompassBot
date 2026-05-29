from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.texts import (
    BTN_ADD_INCOME,
    BTN_ADD_OBLIGATION,
    BTN_BACK,
    BTN_CANCEL_ACTION,
    BTN_EDIT,
    BTN_IM_BACK,
    BTN_MARK_PAYMENT,
    BTN_MENU,
    BTN_MY_INCOMES,
    BTN_PROGRESS,
    BTN_SAFE_TO_SPEND,
    BTN_SETTINGS,
    BTN_UPCOMING_PAYMENTS,
)
from app.utils import format_money


def main_menu_keyboard(show_im_back: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_SAFE_TO_SPEND)],
        [KeyboardButton(text=BTN_ADD_INCOME), KeyboardButton(text=BTN_MY_INCOMES)],
        [KeyboardButton(text=BTN_ADD_OBLIGATION), KeyboardButton(text=BTN_UPCOMING_PAYMENTS)],
        [KeyboardButton(text=BTN_MARK_PAYMENT), KeyboardButton(text=BTN_PROGRESS)],
        [KeyboardButton(text=BTN_EDIT), KeyboardButton(text=BTN_SETTINGS)],
    ]
    if show_im_back:
        rows.insert(0, [KeyboardButton(text=BTN_IM_BACK)])
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


def income_recurring_keyboard() -> InlineKeyboardMarkup:
    return _inline([[("Да, каждый месяц", "income_recurring:yes")], [("Нет, разовый доход", "income_recurring:no")]])


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


def edit_income_action_keyboard() -> InlineKeyboardMarkup:
    return _inline(
        [
            [("Изменить статус дохода", "edit:income_status")],
            [("Редактировать данные дохода", "edit:income_fields")],
            [(BTN_BACK, "edit:back")],
        ]
    )


def obligations_inline_keyboard(obligations, prefix: str) -> InlineKeyboardMarkup:
    rows = [[(obligation.title, f"{prefix}:{obligation.id}")] for obligation in obligations]
    rows.append([(BTN_BACK, "back")])
    return _inline(rows)


def incomes_inline_keyboard(incomes, prefix: str) -> InlineKeyboardMarkup:
    rows = [[(f"{income.title} · {income.income_date.strftime('%d.%m.%Y')}", f"{prefix}:{income.id}")] for income in incomes]
    rows.append([(BTN_BACK, "back")])
    return _inline(rows)


def income_status_change_button_text(income) -> str:
    display_date = income.period_date or income.income_date
    return f"{display_date.strftime('%d.%m')} — {income.title} — {format_money(income.amount)}"


def income_status_change_keyboard(incomes) -> InlineKeyboardMarkup:
    rows = [[(income_status_change_button_text(income), f"edit_inc_status_choose:{income.id}")] for income in incomes]
    rows.append([(BTN_BACK, "edit:incomes")])
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


def return_preview_keyboard() -> InlineKeyboardMarkup:
    return _inline([[("Да, обновить данные", "confirm_im_back")], [("Отмена", "cancel_im_back")]])


def return_result_keyboard() -> InlineKeyboardMarkup:
    return _inline(
        [
            [("➕ Добавить доход", "im_back:add_income")],
            [("📅 Ближайшие платежи", "im_back:payments")],
            [(BTN_MENU, "im_back:menu")],
        ]
    )


def dev_reset_confirm_keyboard() -> InlineKeyboardMarkup:
    return _inline([[("Да, сбросить состояние", "dev_confirm_reset_state")], [("Отмена", "dev_cancel")]])


def dev_clear_all_confirm_keyboard() -> InlineKeyboardMarkup:
    return _inline([[("Да, удалить всё", "dev_confirm_clear_all")], [("Отмена", "dev_cancel")]])


def dev_make_incomes_recurring_confirm_keyboard() -> InlineKeyboardMarkup:
    return _inline(
        [[("Да, сделать регулярными", "dev_confirm_make_incomes_recurring")], [("Отмена", "dev_cancel")]]
    )

