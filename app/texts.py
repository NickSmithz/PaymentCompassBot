BTN_FINANCIAL_STATUS = "📍 Финансовый статус"
BTN_SAFE_TO_SPEND = "💰 Сколько можно тратить?"
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

MAIN_MENU_BUTTONS = {
    BTN_FINANCIAL_STATUS,
    BTN_SAFE_TO_SPEND,
    BTN_WHAT_IF_BUY,
    BTN_SALARY_PLAN,
    BTN_LIVING_MINIMUM,
    BTN_ADD_INCOME,
    BTN_MY_INCOMES,
    BTN_ADD_OBLIGATION,
    BTN_UPCOMING_PAYMENTS,
    BTN_SAVINGS,
    BTN_MARK_PAYMENT,
    BTN_PROGRESS,
    BTN_EDIT,
    BTN_SETTINGS,
}

CONTROL_BUTTONS = {
    BTN_CANCEL_ACTION,
    BTN_MENU,
}

NAVIGATION_BUTTONS = MAIN_MENU_BUTTONS | CONTROL_BUTTONS

MAIN_COMMANDS = {
    "/start",
    "/menu",
    "/help",
    "/status",
    "/spend",
    "/what_if_buy",
    "/salary_plan",
    "/living_minimum",
    "/add_income",
    "/incomes",
    "/add_obligation",
    "/payments",
    "/savings",
    "/progress",
    "/cancel",
}


def is_navigation_text(text: str | None) -> bool:
    if not text:
        return False
    stripped = text.strip()
    command = stripped.split(maxsplit=1)[0].split("@", 1)[0]
    return stripped in NAVIGATION_BUTTONS or command in MAIN_COMMANDS
