from app.keyboards import main_menu_keyboard
from app.texts import (
    ACTIVE_MAIN_MENU_BUTTONS,
    BTN_MARK_PAYMENT,
    FROZEN_COMMANDS,
    FROZEN_FEATURE_BUTTONS,
    NAVIGATION_BUTTONS,
)


def _reply_keyboard_texts(markup) -> list[str]:
    return [button.text for row in markup.keyboard for button in row]


def test_mark_payment_is_not_active_navigation():
    assert BTN_MARK_PAYMENT not in ACTIVE_MAIN_MENU_BUTTONS
    assert BTN_MARK_PAYMENT not in NAVIGATION_BUTTONS
    assert BTN_MARK_PAYMENT in FROZEN_FEATURE_BUTTONS


def test_mark_payment_commands_are_frozen():
    assert "/mark_payment" in FROZEN_COMMANDS
    assert "/pay" in FROZEN_COMMANDS
    assert "/payment" in FROZEN_COMMANDS


def test_main_menu_does_not_show_mark_payment_button():
    texts = _reply_keyboard_texts(main_menu_keyboard(show_im_back=True))

    assert BTN_MARK_PAYMENT not in texts
