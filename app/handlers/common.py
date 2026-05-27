import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from app.texts import BTN_CANCEL_ACTION, BTN_EDIT, BTN_MENU, UNKNOWN_COMMAND_TEXT

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.database import SessionLocal
from app.formatters import (
    format_allocation_result,
    format_error,
    format_income_status_update,
    format_plan_recalculated,
    format_reserved_amount_updated,
    format_reserved_amount_validation_error,
)
from app.keyboards import (
    cancel_action_keyboard,
    edit_income_fields_keyboard,
    edit_menu_keyboard,
    edit_obligation_fields_keyboard,
    income_status_edit_keyboard,
    incomes_inline_keyboard,
    main_menu_keyboard,
    obligation_recurring_keyboard,
    obligation_status_keyboard,
    obligations_inline_keyboard,
)
from app.repositories import payments as payments_repo
from app.repositories import reserves as reserves_repo
from app.services import allocation as allocation_service
from app.services import incomes as income_service
from app.services import obligations as obligation_service
from app.services.users import get_or_create_user_from_telegram
from app.states import EditIncomeStates, EditObligationStates
from app.utils import format_money, parse_date, parse_money

router = Router()
logger = logging.getLogger(__name__)


def _today(timezone: str):
    return datetime.now(ZoneInfo(timezone or get_settings().timezone)).date()


def _now(timezone: str):
    return datetime.now(ZoneInfo(timezone or get_settings().timezone))



@router.message(Command("cancel"))
@router.message(F.text == BTN_CANCEL_ACTION)
async def cancel_action(message: Message, state: FSMContext, fsm_was_active: bool = False) -> None:
    current_state = await state.get_state()
    if fsm_was_active or current_state is not None:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())
    else:
        await message.answer("Сейчас нет активного действия.", reply_markup=main_menu_keyboard())


@router.message(F.text == BTN_MENU)
async def menu_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню", reply_markup=main_menu_keyboard())

@router.callback_query(F.data == "back")
async def back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Главное меню", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(F.text == BTN_EDIT)
async def edit_menu(message: Message) -> None:
    await message.answer("Что нужно изменить?", reply_markup=edit_menu_keyboard())


@router.callback_query(F.data == "edit:back")
async def edit_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Главное меню", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "edit:incomes")
async def edit_incomes(callback: CallbackQuery, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        incomes = await income_service.list_incomes(session, user.id)
    if not incomes:
        await callback.message.answer("Пока нет доходов для редактирования.", reply_markup=main_menu_keyboard())
    else:
        await state.set_state(EditIncomeStates.choose)
        await callback.message.answer("Выбери доход:", reply_markup=incomes_inline_keyboard(incomes, "edit_inc"))
    await callback.answer()


@router.callback_query(F.data == "edit:delete_income")
async def choose_income_delete(callback: CallbackQuery, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        incomes = await income_service.list_incomes(session, user.id)
    if not incomes:
        await callback.message.answer("Пока нет доходов для удаления.", reply_markup=main_menu_keyboard())
    else:
        await state.set_state(EditIncomeStates.choose)
        await callback.message.answer("Выбери доход:", reply_markup=incomes_inline_keyboard(incomes, "del_inc"))
    await callback.answer()


@router.callback_query(EditIncomeStates.choose, F.data.startswith("edit_inc:"))
async def edit_income_choose(callback: CallbackQuery, state: FSMContext) -> None:
    income_id = int(callback.data.split(":")[1])
    await state.update_data(income_id=income_id)
    await state.set_state(EditIncomeStates.choose_field)
    await callback.message.answer("Что изменить?", reply_markup=edit_income_fields_keyboard(income_id))
    await callback.answer()


@router.callback_query(EditIncomeStates.choose, F.data.startswith("del_inc:"))
async def delete_income(callback: CallbackQuery, state: FSMContext) -> None:
    income_id = int(callback.data.split(":")[1])
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        await allocation_service.release_reserves_for_income(session, user.id, income_id)
        await income_service.delete_income(session, user.id, income_id)
        await allocation_service.recalculate_user_plan(session, user.id, _today(user.timezone))
    await state.clear()
    await callback.message.answer("Доход удалён. Резервы по нему отменены, рекомендации пересчитаны.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(EditIncomeStates.choose_field, F.data.startswith("edit_inc_field:"))
async def edit_income_field(callback: CallbackQuery, state: FSMContext) -> None:
    _, income_id, field = callback.data.split(":")
    await state.update_data(income_id=int(income_id), field=field)
    if field == "status":
        await callback.message.answer("Выбери новый статус дохода:", reply_markup=income_status_edit_keyboard(int(income_id)))
    else:
        prompts = {
            "title": "Введи новое название дохода.",
            "amount": "Введи новую сумму дохода.",
            "date": "Введи новую дату дохода в формате ДД.ММ.ГГГГ.",
            "source": "Введи источник дохода. Чтобы очистить источник, отправь «-».",
        }
        await state.set_state(EditIncomeStates.new_value)
        await callback.message.answer(prompts.get(field, "Введи новое значение."), reply_markup=cancel_action_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_inc_status:"))
async def edit_income_status(callback: CallbackQuery, state: FSMContext) -> None:
    _, income_id, status = callback.data.split(":")
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        now = _now(user.timezone)
        result = await income_service.update_income_status(
            session,
            user.id,
            int(income_id),
            status,
            now.date(),
            now,
        )
    await state.clear()
    await callback.message.answer(format_income_status_update(result), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(EditIncomeStates.new_value)
async def edit_income_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        if data["field"] == "title":
            update_data = {"title": message.text.strip()}
        elif data["field"] == "amount":
            update_data = {"amount": parse_money(message.text)}
        elif data["field"] == "date":
            update_data = {"income_date": parse_date(message.text, get_settings().timezone)}
        elif data["field"] == "source":
            source = message.text.strip()
            update_data = {"source": None if source == "-" else source}
        else:
            raise ValueError
    except ValueError:
        await message.answer("Не смог разобрать значение. Попробуй ещё раз.", reply_markup=cancel_action_keyboard())
        return

    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        await income_service.update_income(session, user.id, data["income_id"], update_data)
        plan = await allocation_service.recalculate_user_plan(session, user.id, _today(user.timezone))
    await state.clear()
    text = format_allocation_result(plan["allocation"]) if plan["allocation"] else format_plan_recalculated("Доход")
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "edit:obligations")
async def edit_obligations(callback: CallbackQuery, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        obligations = await obligation_service.list_obligations(session, user.id)
    if not obligations:
        await callback.message.answer("Пока нет платежей для редактирования.", reply_markup=main_menu_keyboard())
    else:
        await state.set_state(EditObligationStates.choose)
        await callback.message.answer("Выбери платёж:", reply_markup=obligations_inline_keyboard(obligations, "edit_obl"))
    await callback.answer()


@router.callback_query(F.data == "edit:delete_obligation")
async def choose_obligation_disable(callback: CallbackQuery, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        obligations = await obligation_service.list_obligations(session, user.id)
    if not obligations:
        await callback.message.answer("Пока нет платежей для отключения.", reply_markup=main_menu_keyboard())
    else:
        await state.set_state(EditObligationStates.choose)
        await callback.message.answer("Выбери платёж:", reply_markup=obligations_inline_keyboard(obligations, "del_obl"))
    await callback.answer()


@router.callback_query(EditObligationStates.choose, F.data.startswith("del_obl:"))
async def disable_obligation(callback: CallbackQuery, state: FSMContext) -> None:
    obligation_id = int(callback.data.split(":")[1])
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        await obligation_service.update_obligation_status(session, user.id, obligation_id, False)
        await allocation_service.recalculate_user_plan(session, user.id, _today(user.timezone))
    await state.clear()
    await callback.message.answer("Платёж отключён. Рекомендации пересчитаны.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(EditObligationStates.choose, F.data.startswith("edit_obl:"))
async def edit_obligation_choose(callback: CallbackQuery, state: FSMContext) -> None:
    obligation_id = int(callback.data.split(":")[1])
    await state.update_data(obligation_id=obligation_id)
    await state.set_state(EditObligationStates.choose_field)
    await callback.message.answer("Что изменить?", reply_markup=edit_obligation_fields_keyboard(obligation_id))
    await callback.answer()


@router.callback_query(EditObligationStates.choose_field, F.data.startswith("edit_obl_field:"))
async def edit_obligation_field(callback: CallbackQuery, state: FSMContext) -> None:
    _, obligation_id, field = callback.data.split(":")
    await state.update_data(obligation_id=int(obligation_id), field=field)
    if field == "status":
        await callback.message.answer("Выбери статус платежа:", reply_markup=obligation_status_keyboard(int(obligation_id)))
    elif field == "recurring":
        await callback.message.answer("Платёж повторяется каждый месяц?", reply_markup=obligation_recurring_keyboard(int(obligation_id)))
    elif field == "reserved_amount":
        async with SessionLocal() as session:
            user = await get_or_create_user_from_telegram(
                session,
                callback.from_user.id,
                callback.from_user.username,
                callback.from_user.first_name,
            )
            info = await obligation_service.get_obligation_reserved_amount_info(session, user.id, int(obligation_id))
        if info is None:
            await state.clear()
            await callback.message.answer("Платёж не найден или уже отключён.", reply_markup=main_menu_keyboard())
        else:
            await state.set_state(EditObligationStates.reserved_amount)
            await callback.message.answer(
                f"Сейчас отложено на платёж «{info['obligation'].title}»: {format_money(info['current_reserved_amount'])}.\n\n"
                "Введите новую сумму, которая уже отложена.\n"
                "Например: 10000",
                reply_markup=cancel_action_keyboard(),
            )
    else:
        prompts = {
            "title": "Введи новое название платежа.",
            "type": "Введи тип: credit, credit_card, installment, mortgage, personal_debt, utilities, rent или other.",
            "amount": "Введи новую сумму платежа.",
            "date": "Введи новую ближайшую дату платежа.",
            "debt": "Введи новый остаток долга. Можно 0, если не хочешь указывать.",
            "priority": "Введи приоритет: 1 — высокий, 2 — средний, 3 — обычный.",
        }
        await state.set_state(EditObligationStates.new_value)
        await callback.message.answer(prompts.get(field, "Введи новое значение."), reply_markup=cancel_action_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_obl_status:"))
async def edit_obligation_status(callback: CallbackQuery, state: FSMContext) -> None:
    _, obligation_id, status = callback.data.split(":")
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        await obligation_service.update_obligation_status(session, user.id, int(obligation_id), status == "active")
        await allocation_service.recalculate_user_plan(session, user.id, _today(user.timezone))
    await state.clear()
    await callback.message.answer("Платёж обновлён. Рекомендации пересчитаны.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_obl_recurring:"))
async def edit_obligation_recurring(callback: CallbackQuery, state: FSMContext) -> None:
    _, obligation_id, value = callback.data.split(":")
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        await obligation_service.update_obligation_field(session, user.id, int(obligation_id), "recurring", value == "yes")
        await allocation_service.recalculate_user_plan(session, user.id, _today(user.timezone))
    await state.clear()
    await callback.message.answer("Платёж обновлён. Рекомендации пересчитаны.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(EditObligationStates.reserved_amount)
async def edit_obligation_reserved_amount(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        new_reserved_amount = parse_money(message.text)
    except ValueError:
        await message.answer("Не смог разобрать сумму. Введите сумму ещё раз, например: 10000", reply_markup=cancel_action_keyboard())
        return

    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        try:
            summary = await obligation_service.update_obligation_reserved_amount(
                session,
                user.id,
                data["obligation_id"],
                new_reserved_amount,
                _today(user.timezone),
            )
        except obligation_service.ReservedAmountValidationError as error:
            await message.answer(format_reserved_amount_validation_error(error), reply_markup=cancel_action_keyboard())
            return

    await state.clear()
    if summary is None:
        await message.answer("Платёж не найден или уже отключён.", reply_markup=main_menu_keyboard())
        return
    await message.answer(format_reserved_amount_updated(summary), reply_markup=main_menu_keyboard())


@router.message(EditObligationStates.new_value)
async def edit_obligation_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        field = data["field"]
        if field in {"title", "type"}:
            value = message.text.strip()
        elif field == "amount":
            value = parse_money(message.text)
        elif field == "date":
            value = parse_date(message.text, get_settings().timezone)
        elif field == "debt":
            amount = parse_money(message.text)
            value = amount if amount > 0 else None
        elif field == "priority":
            value = int(message.text.strip())
            if value not in {1, 2, 3}:
                raise ValueError
        else:
            raise ValueError
    except ValueError:
        await message.answer("Не смог разобрать значение. Попробуй ещё раз.", reply_markup=cancel_action_keyboard())
        return

    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        await obligation_service.update_obligation_field(session, user.id, data["obligation_id"], data["field"], value)
        await allocation_service.recalculate_user_plan(session, user.id, _today(user.timezone))
    await state.clear()
    await message.answer("Платёж обновлён. Рекомендации пересчитаны.", reply_markup=main_menu_keyboard())


@router.message(Command("debug_reserves"))
async def debug_reserves(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        transactions = await reserves_repo.list_by_user(session, user.id, limit=20)
        obligations = await obligation_service.list_obligations(session, user.id)
        incomes = await income_service.list_incomes(session, user.id)

        lines = ["🧪 Debug reserves", "", "Последние reserve_transactions:"]
        if not transactions:
            lines.append("Пока нет reserve_transactions.")
        for index, tx in enumerate(transactions, 1):
            lines.extend(
                [
                    f"{index}. id={tx.id}",
                    f"income_id={tx.income_id}",
                    f"obligation_id={tx.obligation_id}",
                    f"transaction_type={tx.transaction_type}",
                    f"source={tx.source}",
                    f"amount={format_money(tx.amount)}",
                    f"comment={tx.comment or '-'}",
                    "",
                ]
            )

        lines.extend(["", "Агрегация по платежам:"])
        if not obligations:
            lines.append("Платежей нет.")
        for obligation in obligations:
            raw_reserved = await reserves_repo.sum_reserved_for_obligation(session, user.id, obligation.id)
            paid = await payments_repo.sum_paid_for_obligation_period(
                session,
                obligation.id,
                None,
                obligation.next_payment_date,
            )
            display_reserved = min(raw_reserved, max(0, obligation.monthly_payment_amount - paid))
            remaining = max(0, obligation.monthly_payment_amount - display_reserved - paid)
            lines.extend(
                [
                    f"{obligation.title}",
                    f"required={format_money(obligation.monthly_payment_amount)}",
                    f"reserved_sum={format_money(raw_reserved)}",
                    f"paid={format_money(paid)}",
                    f"remaining={format_money(remaining)}",
                    "",
                ]
            )

        lines.extend(["", "Агрегация по доходам:"])
        if not incomes:
            lines.append("Доходов нет.")
        for income in incomes:
            reserved = await reserves_repo.sum_auto_reserved_for_income(session, user.id, income.id)
            lines.extend(
                [
                    f"{income.title}",
                    f"income_id={income.id}",
                    f"auto_plan_reserved_sum={format_money(reserved)}",
                    "",
                ]
            )

    await message.answer("\n".join(lines).strip(), reply_markup=main_menu_keyboard())


@router.message(Command("debug_incomes"))
async def debug_incomes(message: Message) -> None:
    if not get_settings().dev_mode:
        await message.answer("Команда доступна только в режиме разработки.", reply_markup=main_menu_keyboard())
        return

    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        incomes = await income_service.list_incomes(session, user.id)

    lines = ["🧪 Debug incomes", ""]
    if not incomes:
        lines.append("Доходов нет.")
    for income in incomes:
        received_at = income.received_at.strftime("%Y-%m-%d %H:%M") if income.received_at else "NULL"
        updated_at = income.updated_at.strftime("%Y-%m-%d %H:%M") if income.updated_at else "NULL"
        created_at = income.created_at.strftime("%Y-%m-%d %H:%M") if income.created_at else "NULL"
        lines.extend(
            [
                f"id={income.id} title={income.title} amount={format_money(income.amount)}",
                f"income_date={income.income_date} status={income.status}",
                f"received_at={received_at}",
                f"updated_at={updated_at}",
                f"created_at={created_at}",
                "",
            ]
        )

    await message.answer("\n".join(lines).strip(), reply_markup=main_menu_keyboard())


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(UNKNOWN_COMMAND_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query()
async def callback_fallback(callback: CallbackQuery) -> None:
    await callback.answer("Действие больше не актуально. Открой меню заново.", show_alert=False)
    if callback.message:
        await callback.message.answer("Это действие больше не актуально. Вернись в меню командой /menu.", reply_markup=main_menu_keyboard())


@router.errors()
async def errors_handler(event) -> None:
    logger.exception("Unhandled bot error", exc_info=event.exception)
    update = event.update
    message = getattr(update, "message", None) or getattr(update, "callback_query", None)
    target = message.message if getattr(message, "message", None) else message
    if target:
        await target.answer(format_error(), reply_markup=main_menu_keyboard())




