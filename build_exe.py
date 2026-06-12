"""Build a standalone .exe using PyInstaller.

Usage:
    uv run build_exe.py

Requires PyInstaller (installed automatically via uv):
    uv add --dev pyinstaller
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ENTRY_POINT = ROOT / "run.py"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
ICON = ROOT / "icon.ico"

# Use the same Python that uv is running
python = sys.executable

# Ensure PyInstaller is available
try:
    import PyInstaller  # noqa: F401
except ImportError:
    print("PyInstaller not found. Install it with:  uv add --dev pyinstaller")
    sys.exit(1)

cmd = [
    python, "-m", "PyInstaller",
    "--onefile",
    "--name", "threads-cleaner",
    "--distpath", str(DIST_DIR),
    "--workpath", str(BUILD_DIR),
    "--specpath", str(ROOT),
    "--paths", str(ROOT / "src"),
    "--hidden-import", "playwright",
    "--hidden-import", "playwright.sync_api",
    "--hidden-import", "typer",
    "--hidden-import", "rich",
    "--hidden-import", "threads_cleaner",
    "--hidden-import", "threads_cleaner.main",
    "--hidden-import", "threads_cleaner.browser",
    "--hidden-import", "threads_cleaner.config",
    "--collect-all", "playwright",
    "--collect-all", "typer",
    "--collect-all", "rich",
]

if ICON and ICON.exists():
    cmd.extend(["--icon", str(ICON)])

cmd.append(str(ENTRY_POINT))

print(f"Building threads-cleaner.exe ...")
print(f"  Entry point : {ENTRY_POINT}")
print(f"  Output dir  : {DIST_DIR}")
print(f"  One-file    : yes")
subprocess.run(cmd, check=True)
print(f"\nDone! Exe at: {DIST_DIR / 'threads-cleaner.exe'}")
