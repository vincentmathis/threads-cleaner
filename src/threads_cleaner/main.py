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
    older_than: Optional[str] = typer.Option(
        None, "--older-than", help="Only delete items older than this (e.g. 30d, 7d, 24h, 2w, 1m)."
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
            older_than=older_than,
        )
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


@app.command()
def install_browser():
    """Install the Chromium browser required by Playwright."""
    import subprocess, sys, os
    from shutil import which

    console.print("[yellow]Installing Chromium browser for Playwright...[/]")
    try:
        # Try `playwright` CLI from PATH first
        pw = which("playwright")
        if pw:
            subprocess.run([pw, "install", "chromium"], check=True)
            console.print("[green]Chromium installed![/]")
            return

        # Try system python -m playwright
        for python in ("python3", "python"):
            py = which(python)
            if py:
                try:
                    subprocess.run([py, "-m", "playwright", "install", "chromium"], check=True)
                    console.print("[green]Chromium installed![/]")
                    return
                except: pass

        # Fallback: use bundled Playwright's Node.js driver directly
        from playwright._impl._driver import compute_driver_executable, get_driver_env
        driver_exe, driver_cli = compute_driver_executable()
        env = get_driver_env()
        # Point browser install to the user profile (not the PyInstaller temp dir)
        pw_browsers = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "ms-playwright")
        env["PLAYWRIGHT_BROWSERS_PATH"] = pw_browsers
        result = subprocess.run(
            [driver_exe, driver_cli, "install", "chromium"],
            env=env, capture_output=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"driver exited with code {result.returncode}")
        console.print("[green]Chromium installed![/]")
    except Exception as e:
        console.print(f"[red]Installation failed: {e}[/]")
        console.print("Try manually from a terminal with Python+Playwright: [bold]playwright install chromium[/]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
