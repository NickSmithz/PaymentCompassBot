from app.telegram_messages import split_text_by_lines


def test_short_text_is_not_split():
    assert split_text_by_lines("short text", chunk_size=100) == ["short text"]


def test_long_text_is_split_into_multiple_chunks():
    text = "\n".join([f"line-{index}" for index in range(20)])

    chunks = split_text_by_lines(text, chunk_size=30)

    assert len(chunks) > 1


def test_no_chunk_exceeds_chunk_size():
    text = "\n".join([f"line-{index}" for index in range(50)])

    chunks = split_text_by_lines(text, chunk_size=25)

    assert all(len(chunk) <= 25 for chunk in chunks)


def test_lines_are_not_lost():
    lines = [f"line-{index}" for index in range(15)]
    text = "\n".join(lines)

    chunks = split_text_by_lines(text, chunk_size=20)
    restored_lines = "\n".join(chunks).splitlines()

    assert restored_lines == lines


def test_single_overlong_line_is_hard_split():
    text = "x" * 26

    chunks = split_text_by_lines(text, chunk_size=10)

    assert chunks == ["x" * 10, "x" * 10, "x" * 6]
