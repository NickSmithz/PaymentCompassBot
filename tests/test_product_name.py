from pathlib import Path


FORBIDDEN_PATTERNS = [
    "Анти" + "Просрочка",
    "анти" + "просрочка",
    "anti" + "_prosrochka",
    "anti" + "-prosrochka",
    "Anti" + "Prosrochka",
    "Anti " + "Prosrochka",
]

TEXT_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".example"}


def test_old_product_name_not_used():
    root = Path(__file__).resolve().parents[1]
    ignored_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
    matches = []

    for path in root.rglob("*"):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix not in TEXT_EXTENSIONS and path.name != ".env.example":
            continue

        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                matches.append(f"{path}: contains {pattern!r}")

    assert not matches, "Old product name found:\n" + "\n".join(matches)
