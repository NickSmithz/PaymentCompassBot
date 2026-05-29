BTN_FINANCIAL_STATUS = "📍 Финансовый статус"
BTN_SAFE_TO_SPEND = "💰 Сколько можно тратить?"
BTN_IM_BACK = "🔄 Я вернулся"
BTN_WHAT_IF_BUY = "🛒 Что если купить?"
BTN_SALARY_PLAN = "📆 План до зарплаты"
BTN_LIVING_MINIMUM = "🛟 Минимум на жизнь"

BTN_ADD_INCOME = "➕ Добавить доход"
BTN_MY_INCOMES = "💵 Мои доходы"
BTN_ADD_OBLIGATION = "➕ Добавить платёж"
BTN_UPCOMING_PAYMENTS = "📅 Ближайшие платежи"

BTN_SAVINGS = "🏦 Накопления"
BTN_MARK_PAYMENT = "✅ Отметить оплату"
BTN_PROGRESS = "📊 Прогресс долгов"
BTN_EDIT = "✏️ Редактировать"
BTN_SETTINGS = "⚙️ Настройки"

BTN_BACK = "⬅️ Назад"
BTN_MENU = "🏠 В меню"
BTN_CANCEL_ACTION = "❌ Отменить действие"

STATUS_RECEIVED = "✅ уже пришёл"
STATUS_EXPECTED = "⏳ ожидается"
STATUS_CANCELLED = "❌ отменён"

RISK_LOW = "🟢 низкий"
RISK_MEDIUM = "🟡 средний"
RISK_HIGH = "🔴 высокий"

UNKNOWN_COMMAND_TEXT = "Не понял команду. Вернись в меню или напиши /help."

ACTIVE_MAIN_MENU_BUTTONS = {
    BTN_SAFE_TO_SPEND,
    BTN_ADD_INCOME,
    BTN_MY_INCOMES,
    BTN_ADD_OBLIGATION,
    BTN_UPCOMING_PAYMENTS,
    BTN_EDIT,
    BTN_SETTINGS,
}

FROZEN_FEATURE_BUTTONS = {
    BTN_FINANCIAL_STATUS,
    BTN_WHAT_IF_BUY,
    BTN_SALARY_PLAN,
    BTN_LIVING_MINIMUM,
    BTN_SAVINGS,
    BTN_MARK_PAYMENT,
    BTN_PROGRESS,
}

MAIN_MENU_BUTTONS = ACTIVE_MAIN_MENU_BUTTONS

CONTROL_BUTTONS = {
    BTN_CANCEL_ACTION,
    BTN_MENU,
}

NAVIGATION_BUTTONS = ACTIVE_MAIN_MENU_BUTTONS | CONTROL_BUTTONS
NAVIGATION_BUTTONS = NAVIGATION_BUTTONS | {BTN_IM_BACK}

CMD_IM_BACK = "/im_back"

ACTIVE_COMMANDS = {
    "/start",
    "/menu",
    "/help",
    "/add_income",
    "/incomes",
    "/add_obligation",
    "/payments",
    "/spend",
    CMD_IM_BACK,
    "/cancel",
}

FROZEN_COMMANDS = {
    "/status",
    "/what_if_buy",
    "/salary_plan",
    "/living_minimum",
    "/savings",
    "/mark_payment",
    "/pay",
    "/payment",
    "/progress",
}

MAIN_COMMANDS = ACTIVE_COMMANDS

FROZEN_FEATURE_MESSAGE = (
    "Эта функция временно отключена.\n\n"
    "Сейчас мы стабилизируем основной функционал:\n"
    "— доходы;\n"
    "— платежи;\n"
    "— резервирование;\n"
    "— ближайшие платежи;\n"
    "— сколько можно тратить.\n\n"
    "Она вернётся позже, когда ядро будет работать стабильно."
)

FROZEN_PAYMENT_MESSAGE = (
    "Функция «Отметить оплату» временно отключена.\n\n"
    "В текущей версии бот считает платёж закрытым для планирования, когда нужная сумма полностью "
    "зарезервирована. Если сумма собрана, отдельное подтверждение оплаты не требуется."
)

FROZEN_PROGRESS_MESSAGE = (
    "Функция «Прогресс долгов» временно отключена.\n\n"
    "Сейчас мы стабилизируем основной расчёт:\n"
    "— доходы;\n"
    "— платежи;\n"
    "— резервирование;\n"
    "— ближайшие платежи;\n"
    "— сколько можно тратить.\n\n"
    "Раздел прогресса долгов вернётся позже в более точном виде."
)


def is_navigation_text(text: str | None) -> bool:
    if not text:
        return False
    stripped = text.strip()
    command = stripped.split(maxsplit=1)[0].split("@", 1)[0]
    return stripped in NAVIGATION_BUTTONS or command in MAIN_COMMANDS
