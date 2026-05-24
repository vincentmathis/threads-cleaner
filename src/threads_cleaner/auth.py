from __future__ import annotations

from rich.console import Console

from threads_cleaner import config

console = Console()


def get_session() -> dict:
    session = config.load_session()
    if not session:
        raise RuntimeError("Not logged in. Run:  threads-cleaner browser-login")
    return session
