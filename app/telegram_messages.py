import logging

logger = logging.getLogger(__name__)


def split_text_by_lines(text: str, chunk_size: int = 3500) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not text:
        return []

    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    def flush_current() -> None:
        nonlocal current_lines, current_length
        if current_lines:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_length = 0

    for line in text.splitlines():
        if len(line) > chunk_size:
            flush_current()
            for start in range(0, len(line), chunk_size):
                chunks.append(line[start : start + chunk_size])
            continue

        separator_length = 1 if current_lines else 0
        next_length = current_length + separator_length + len(line)
        if current_lines and next_length > chunk_size:
            flush_current()
            next_length = len(line)

        current_lines.append(line)
        current_length = next_length

    flush_current()
    return [chunk for chunk in chunks if chunk]


async def send_long_message(
    message,
    text: str,
    reply_markup=None,
    chunk_size: int = 3500,
) -> None:
    from aiogram.exceptions import TelegramBadRequest

    chunks = split_text_by_lines(text, chunk_size)
    if not chunks:
        return

    logger.info("Sending long message: length=%s chunks=%s", len(text), len(chunks))
    for index, chunk in enumerate(chunks):
        markup = reply_markup if index == len(chunks) - 1 else None
        try:
            await message.answer(chunk, reply_markup=markup)
        except TelegramBadRequest as exc:
            if "message is too long" not in str(exc):
                raise
            smaller_chunks = split_text_by_lines(chunk, max(1, chunk_size // 2))
            for sub_index, smaller_chunk in enumerate(smaller_chunks):
                sub_markup = markup if sub_index == len(smaller_chunks) - 1 else None
                await message.answer(smaller_chunk, reply_markup=sub_markup)
