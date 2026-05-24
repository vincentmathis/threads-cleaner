from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from threads_cleaner.browser import run_browser_delete, run_browser_login

app     = typer.Typer(help="Bulk-delete your Threads posts and replies via browser automation.")
console = Console()


@app.command()
def browser_login():
    """Log in via a browser window (no manual cookie copying)."""
    try:
        run_browser_login()
        console.print("Run [bold]threads-cleaner browser-delete --headed[/] to test it.")
    except Exception as e:
        console.print(f"[red]Login failed:[/] {e}")
        raise typer.Exit(1)


@app.command()
def browser_delete(
    include_replies: bool = typer.Option(
        False, "--include-replies", help="Also delete replies from the Replies tab."
    ),
    max_deletes: Optional[int] = typer.Option(
        None, "--max", "-m", help="Stop after deleting this many items (0 = unlimited)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview without deleting."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the confirmation prompt."
    ),
    headed: bool = typer.Option(
        False, "--headed", help="Show the browser window (for debugging)."
    ),
):
    """Delete posts (and optionally replies) via a real browser (Playwright). Clicks the UI like a human."""
    try:
        run_browser_delete(
            include_replies=include_replies,
            max_deletes=max_deletes,
            dry_run=dry_run,
            yes=yes,
            headed=headed,
        )
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


@app.command()
def install_browser():
    """Install the Chromium browser required by Playwright."""
    import subprocess, sys
    console.print("[yellow]Installing Chromium browser for Playwright...[/]")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=False,
    )
    if result.returncode == 0:
        console.print("[green]Chromium installed![/] Run [bold]threads-cleaner browser-login[/] to start.")
    else:
        console.print("[red]Installation failed.[/] Try manually: [bold]playwright install chromium[/]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
