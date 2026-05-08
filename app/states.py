from aiogram.fsm.state import State, StatesGroup


class AddObligationStates(StatesGroup):
    title = State()
    type = State()
    amount = State()
    next_payment_date = State()
    is_recurring = State()
    total_debt_amount = State()
    already_reserved_amount = State()
    priority = State()


class AddIncomeStates(StatesGroup):
    title = State()
    amount = State()
    income_date = State()
    status = State()


class PaymentStates(StatesGroup):
    choose_obligation = State()
    amount = State()
    paid_at = State()


class EditObligationStates(StatesGroup):
    choose = State()
    choose_field = State()
    new_value = State()


class EditIncomeStates(StatesGroup):
    choose = State()
    choose_field = State()
    new_value = State()


class SavingsStates(StatesGroup):
    percent = State()


class LivingMinimumStates(StatesGroup):
    amount = State()


class WhatIfPurchaseStates(StatesGroup):
    amount = State()
