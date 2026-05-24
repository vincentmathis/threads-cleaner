import json
from pathlib import Path

# Session storage
CONFIG_DIR = Path.home() / ".config" / "threads-cleaner"
SESSION_FILE = CONFIG_DIR / "session.json"


def save_session(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data, indent=2))
    SESSION_FILE.chmod(0o600)


def load_session() -> dict | None:
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return None


def clear_session() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
