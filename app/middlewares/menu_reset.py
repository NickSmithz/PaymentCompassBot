from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

from app.texts import MAIN_COMMANDS, NAVIGATION_BUTTONS


class MainMenuResetMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text:
            state: FSMContext | None = data.get("state")
            if state is not None:
                text = event.text.strip()
                command = text.split(maxsplit=1)[0].split("@", 1)[0]
                if text in NAVIGATION_BUTTONS or command in MAIN_COMMANDS:
                    current_state = await state.get_state()
                    data["fsm_was_active"] = current_state is not None
                    if current_state is not None:
                        await state.clear()
        return await handler(event, data)
