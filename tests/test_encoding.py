from pathlib import Path


BAD_PATTERNS = [
    "\u00d0",
    "\u00d1",
    "\u00f0\u0178",
    "\u00e2\u017e",
    "\u00e2\u0153",
    "\u00e2\u0161",
    "\u00e2\u20ac\u201d",
    "\u00e2\u20ac\u201c",
    "\ufffd",
]
TEXT_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".env", ".example"}


def test_no_mojibake_patterns():
    root = Path(__file__).resolve().parents[1]
    ignored_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
    bad_matches = []

    for path in root.rglob("*"):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix not in TEXT_EXTENSIONS and path.name != ".env.example":
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            bad_matches.append(f"{path}: cannot decode as UTF-8")
            continue

        for pattern in BAD_PATTERNS:
            if pattern in text:
                bad_matches.append(f"{path}: contains {pattern!r}")

    assert not bad_matches, "Mojibake or non-UTF-8 files found:\n" + "\n".join(bad_matches)
